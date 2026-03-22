package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"go.mau.fi/whatsmeow"
	waProto "go.mau.fi/whatsmeow/binary/proto"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
	"google.golang.org/protobuf/proto"
)

type IncomingMessage struct {
	From string `json:"from"`
	Text string `json:"text"`
	ID   string `json:"id"`
}

var (
	client   *whatsmeow.Client
	msgQueue []IncomingMessage
	mu       sync.Mutex
	latestQR string
	qrMu     sync.RWMutex
)

func eventHandler(evt interface{}) {
	switch v := evt.(type) {
	case *events.Message:
		if v.Info.IsFromMe {
			return
		}
		text := ""
		if v.Message.GetConversation() != "" {
			text = v.Message.GetConversation()
		} else if v.Message.GetExtendedTextMessage() != nil {
			text = v.Message.GetExtendedTextMessage().GetText()
		}
		if text == "" {
			return
		}
		mu.Lock()
		msgQueue = append(msgQueue, IncomingMessage{
			From: v.Info.Sender.String(),
			Text: text,
			ID:   v.Info.ID,
		})
		mu.Unlock()
		log.Printf("Message from %s: %s", v.Info.Sender.String(), text)
	}
}

func connectLoop(ctx context.Context, dbPath string) {
	for {
		if ctx.Err() != nil {
			return
		}

		dbLog := waLog.Stdout("Database", "WARN", true)
		container, err := sqlstore.New(ctx, "sqlite3", "file:"+dbPath+"?_foreign_keys=on", dbLog)
		if err != nil {
			log.Printf("DB init failed: %v — retrying in 5s", err)
			time.Sleep(5 * time.Second)
			continue
		}
		deviceStore, err := container.GetFirstDevice(ctx)
		if err != nil {
			log.Printf("Device store failed: %v — retrying in 5s", err)
			time.Sleep(5 * time.Second)
			continue
		}
		clientLog := waLog.Stdout("Client", "WARN", true)
		c := whatsmeow.NewClient(deviceStore, clientLog)
		c.AddEventHandler(eventHandler)

		if c.Store.ID == nil {
			// Not logged in — QR flow
			qrChan, _ := c.GetQRChannel(ctx)
			if err = c.Connect(); err != nil {
				log.Printf("Connect failed: %v — retrying in 5s", err)
				time.Sleep(5 * time.Second)
				continue
			}
			mu.Lock()
			client = c
			mu.Unlock()

			linked := false
			for evt := range qrChan {
				if evt.Event == "code" {
					qrMu.Lock()
					latestQR = evt.Code
					qrMu.Unlock()
					log.Printf("QR ready — open http://<pi-ip>:8181/qr to scan")
				} else if evt.Event == "success" {
					log.Printf("QR scanned — logged in!")
					qrMu.Lock()
					latestQR = ""
					qrMu.Unlock()
					linked = true
				} else {
					log.Printf("QR event: %s", evt.Event)
				}
			}
			if !linked {
				log.Printf("QR timeout — restarting login flow in 3s")
				c.Disconnect()
				mu.Lock()
				client = nil
				mu.Unlock()
				time.Sleep(3 * time.Second)
				continue
			}
			// Linked — client stays connected, fall through to keepalive
		} else {
			// Already have session — reconnect
			if err = c.Connect(); err != nil {
				log.Printf("Reconnect failed: %v — retrying in 5s", err)
				time.Sleep(5 * time.Second)
				continue
			}
			mu.Lock()
			client = c
			mu.Unlock()
			log.Printf("Reconnected with stored session")
		}

		// Keep alive — wait until disconnected then reconnect
		for {
			if ctx.Err() != nil {
				return
			}
			if !c.IsConnected() {
				log.Printf("Client disconnected — reconnecting in 5s")
				c.Disconnect()
				mu.Lock()
				client = nil
				mu.Unlock()
				time.Sleep(5 * time.Second)
				break
			}
			time.Sleep(5 * time.Second)
		}
	}
}

func main() {
	port := os.Getenv("WA_BRIDGE_PORT")
	if port == "" {
		port = "8181"
	}
	dbPath := os.Getenv("WA_BRIDGE_DB")
	if dbPath == "" {
		dbPath = "/var/lib/wabridge/wabridge.db"
	}
	os.MkdirAll("/var/lib/wabridge", 0700)

	ctx := context.Background()
	go connectLoop(ctx, dbPath)

	http.HandleFunc("/qr", func(w http.ResponseWriter, r *http.Request) {
		qrMu.RLock()
		qr := latestQR
		qrMu.RUnlock()
		w.Header().Set("Content-Type", "text/html")
		mu.Lock()
		c := client
		mu.Unlock()
		if c != nil && c.IsLoggedIn() {
			fmt.Fprintln(w, "<h2 style='font-family:sans-serif;text-align:center;padding:40px'>Already linked!</h2>")
			return
		}
		if qr == "" {
			fmt.Fprintln(w, "<h3 style='font-family:sans-serif;text-align:center;padding:40px'>Generating QR... refresh in a moment.</h3><meta http-equiv='refresh' content='3'>")
			return
		}
		fmt.Fprintf(w, `<!DOCTYPE html><html><head>
<meta http-equiv="refresh" content="15">
<title>WhatsApp QR</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
</head><body style="font-family:sans-serif;text-align:center;padding:40px">
<h2>Scan with WhatsApp</h2>
<p>WhatsApp &rarr; Settings &rarr; Linked Devices &rarr; Link a Device</p>
<div id="qr" style="display:inline-block"></div>
<p><small>Page auto-refreshes every 15s</small></p>
<script>new QRCode(document.getElementById("qr"), {text: %q, width:300, height:300});</script>
</body></html>`, qr)
	})

	http.HandleFunc("/messages", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		msgs := msgQueue
		msgQueue = nil
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		if msgs == nil {
			fmt.Fprintln(w, "[]")
			return
		}
		json.NewEncoder(w).Encode(msgs)
	})

	http.HandleFunc("/send", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			To   string `json:"to"`
			Text string `json:"text"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "bad request", 400)
			return
		}
		mu.Lock()
		c := client
		mu.Unlock()
		if c == nil || !c.IsLoggedIn() {
			http.Error(w, "not logged in", 503)
			return
		}
		jid, err := types.ParseJID(req.To)
		if err != nil {
			http.Error(w, "bad jid: "+err.Error(), 400)
			return
		}
		msg := &waProto.Message{Conversation: proto.String(req.Text)}
		_, err = c.SendMessage(ctx, jid, msg)
		if err != nil {
			http.Error(w, "send failed: "+err.Error(), 500)
			return
		}
		w.WriteHeader(200)
		fmt.Fprintln(w, "ok")
	})

	http.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		mu.Lock()
		c := client
		mu.Unlock()
		connected := c != nil && c.IsConnected()
		loggedIn := c != nil && c.IsLoggedIn()
		json.NewEncoder(w).Encode(map[string]bool{
			"connected": connected,
			"logged_in": loggedIn,
		})
	})

	log.Printf("WhatsApp bridge listening on :%s — open http://<pi-ip>:%s/qr to scan", port, port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
