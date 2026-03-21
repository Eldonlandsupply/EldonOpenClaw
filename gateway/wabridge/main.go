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

func connectWithQRLoop(ctx context.Context, dbPath string) {
	for {
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
		client = whatsmeow.NewClient(deviceStore, clientLog)
		client.AddEventHandler(eventHandler)

		if client.Store.ID == nil {
			// Not logged in — get QR channel and connect
			qrChan, _ := client.GetQRChannel(ctx)
			err = client.Connect()
			if err != nil {
				log.Printf("Connect failed: %v — retrying in 5s", err)
				time.Sleep(5 * time.Second)
				continue
			}
			linked := false
			for evt := range qrChan {
				if evt.Event == "code" {
					qrMu.Lock()
					latestQR = evt.Code
					qrMu.Unlock()
					log.Printf("QR ready — open http://<pi-ip>:8181/qr to scan")
				} else if evt.Event == "success" {
					log.Printf("QR scanned — logged in!")
					linked = true
				} else {
					log.Printf("QR event: %s", evt.Event)
				}
			}
			if !linked {
				// QR timed out — disconnect and retry the whole flow
				log.Printf("QR timeout — restarting login flow in 3s")
				client.Disconnect()
				qrMu.Lock()
				latestQR = ""
				qrMu.Unlock()
				time.Sleep(3 * time.Second)
				continue
			}
		} else {
			err = client.Connect()
			if err != nil {
				log.Printf("Connect failed: %v — retrying in 5s", err)
				time.Sleep(5 * time.Second)
				continue
			}
			log.Printf("Reconnected with stored session")
		}
		// Connected — block until disconnected
		<-ctx.Done()
		return
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

	// Start QR/connect loop in background
	go connectWithQRLoop(ctx, dbPath)

	// QR web page — auto-refreshes every 15s
	http.HandleFunc("/qr", func(w http.ResponseWriter, r *http.Request) {
		qrMu.RLock()
		qr := latestQR
		qrMu.RUnlock()
		w.Header().Set("Content-Type", "text/html")
		if client != nil && client.IsLoggedIn() {
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
<p><small>Page auto-refreshes every 15s for a fresh QR code</small></p>
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
		if client == nil || !client.IsLoggedIn() {
			http.Error(w, "not logged in", 503)
			return
		}
		jid, err := types.ParseJID(req.To)
		if err != nil {
			http.Error(w, "bad jid: "+err.Error(), 400)
			return
		}
		msg := &waProto.Message{Conversation: proto.String(req.Text)}
		_, err = client.SendMessage(ctx, jid, msg)
		if err != nil {
			http.Error(w, "send failed: "+err.Error(), 500)
			return
		}
		w.WriteHeader(200)
		fmt.Fprintln(w, "ok")
	})

	http.HandleFunc("/status", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		connected := client != nil && client.IsConnected()
		loggedIn := client != nil && client.IsLoggedIn()
		json.NewEncoder(w).Encode(map[string]bool{
			"connected": connected,
			"logged_in": loggedIn,
		})
	})

	log.Printf("WhatsApp bridge listening on :%s — open http://<pi-ip>:%s/qr to scan", port, port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
