package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"

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
	client      *whatsmeow.Client
	msgQueue    []IncomingMessage
	mu          sync.Mutex
	latestQR    string
	qrMu        sync.RWMutex
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

func main() {
	ctx := context.Background()

	port := os.Getenv("WA_BRIDGE_PORT")
	if port == "" {
		port = "8181"
	}
	dbPath := os.Getenv("WA_BRIDGE_DB")
	if dbPath == "" {
		dbPath = "/var/lib/wabridge/wabridge.db"
	}
	os.MkdirAll("/var/lib/wabridge", 0700)

	dbLog := waLog.Stdout("Database", "WARN", true)
	container, err := sqlstore.New(ctx, "sqlite3", "file:"+dbPath+"?_foreign_keys=on", dbLog)
	if err != nil {
		log.Fatalf("DB init failed: %v", err)
	}
	deviceStore, err := container.GetFirstDevice(ctx)
	if err != nil {
		log.Fatalf("Device store failed: %v", err)
	}
	clientLog := waLog.Stdout("Client", "WARN", true)
	client = whatsmeow.NewClient(deviceStore, clientLog)
	client.AddEventHandler(eventHandler)

	if client.Store.ID == nil {
		qrChan, _ := client.GetQRChannel(ctx)
		err = client.Connect()
		if err != nil {
			log.Fatalf("Connect failed: %v", err)
		}
		go func() {
			for evt := range qrChan {
				if evt.Event == "code" {
					qrMu.Lock()
					latestQR = evt.Code
					qrMu.Unlock()
					log.Printf("New QR code ready — open http://<pi-ip>:%s/qr to scan", port)
				} else {
					log.Printf("QR event: %s", evt.Event)
				}
			}
		}()
	} else {
		err = client.Connect()
		if err != nil {
			log.Fatalf("Connect failed: %v", err)
		}
	}

	// QR web page — renders scannable QR via qrcode.js
	http.HandleFunc("/qr", func(w http.ResponseWriter, r *http.Request) {
		qrMu.RLock()
		qr := latestQR
		qrMu.RUnlock()
		if qr == "" && client.IsLoggedIn() {
			fmt.Fprintln(w, "<h2>Already logged in!</h2>")
			return
		}
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<!DOCTYPE html><html><head>
<meta http-equiv="refresh" content="20">
<title>WhatsApp QR</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
</head><body style="font-family:sans-serif;text-align:center;padding:40px">
<h2>Scan with WhatsApp</h2>
<p>WhatsApp → Settings → Linked Devices → Link a Device</p>
<div id="qr"></div>
<p><small>Page auto-refreshes every 20s for new QR codes</small></p>
<script>new QRCode(document.getElementById("qr"), {text: %q, width:256, height:256});</script>
</body></html>`, qr)
	})

	http.HandleFunc("/messages", func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		msgs := msgQueue
		msgQueue = nil
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
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
		json.NewEncoder(w).Encode(map[string]bool{
			"connected": client.IsConnected(),
			"logged_in": client.IsLoggedIn(),
		})
	})

	log.Printf("WhatsApp bridge listening on :%s — open http://<pi-ip>:%s/qr to scan", port, port)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
