import { makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } from '@whiskeysockets/baileys';
import { Redis } from 'ioredis';
import pino from 'pino';
import qrcode from 'qrcode-terminal';
import NodeCache from 'node-cache';

const logger = pino({ level: 'info' });

const redis = new Redis({
    host: process.env.REDIS_HOST || 'redis',
    port: process.env.REDIS_PORT || 6379,
    db: 1,
    retryStrategy: (times) => Math.min(times * 50, 2000),
    maxRetriesPerRequest: 3,
});

const sockets = {};
const reconnectTimers = {};
const msgCache = new NodeCache({ stdTTL: 300 });

// ---------------------------------------------------------------------------
// Start bot for a single restaurant
// ---------------------------------------------------------------------------
async function startBot(rid, phoneNumber) {
    if (reconnectTimers[rid]) {
        clearTimeout(reconnectTimers[rid]);
        delete reconnectTimers[rid];
    }

    const authDir = `/app/auth/${rid}`;
    const { state, saveCreds } = await useMultiFileAuthState(authDir);
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        version,
        auth: state,
        logger,
        printQRInTerminal: false,  // We handle QR ourselves
        browser: [rid, 'Chrome', '1.0.0'],
        markOnlineOnConnect: true,
        syncFullHistory: false,
    });

    sockets[rid] = sock;

    // ---- Connection updates (QR + Pairing Code + Status) ----
    sock.ev.on('connection.update', async (update) => {
        const { connection, qr, lastDisconnect } = update;
        
        // QR code received → display and request pairing code
        if (qr) {
            console.log(`\n📱 QR for ${rid} (${phoneNumber}):`);
            qrcode.generate(qr, { small: true });

            // Store QR string in Redis for web display
            await redis.hset('whatsapp:setup', rid, JSON.stringify({
                qr: qr,
                phoneNumber: phoneNumber,
                status: 'waiting_scan',
                timestamp: Date.now(),
            }));

            // Request pairing code (8-character code)
            // This is the code users can type instead of scanning
            try {
                const code = await sock.requestPairingCode(phoneNumber);
                console.log(`🔢 Pairing code for ${rid}: ${code}`);

                // Store pairing code in Redis
                await redis.hset('whatsapp:setup', rid, JSON.stringify({
                    qr: qr,
                    pairingCode: code,
                    phoneNumber: phoneNumber,
                    status: 'waiting_scan',
                    timestamp: Date.now(),
                }));

                console.log(`📋 Share this code with ${rid}: ${code}`);
                console.log(`   Open WhatsApp → Settings → Linked Devices → Link a Device`);
                console.log(`   Enter code: ${code}`);
            } catch (err) {
                console.log(`⚠️ Could not get pairing code for ${rid}: ${err.message}`);
                console.log(`   Use QR code instead.`);
            }
        }
        
        if (connection === 'open') {
            console.log(`✅ ${rid} connected!`);
            redis.hset('whatsapp:status', rid, 'online');
            // Clear setup data since it's now connected
            redis.hdel('whatsapp:setup', rid);
        }
        
        if (connection === 'close') {
            redis.hset('whatsapp:status', rid, 'offline');
            delete sockets[rid];
            
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            
            if (statusCode === DisconnectReason.loggedOut) {
                console.log(`🚫 ${rid} logged out — needs re-scan`);
                redis.hset('whatsapp:status', rid, 'logged_out');
                return;
            }
            
            const delay = Math.min(1000 * Math.pow(2, reconnectTimers[rid] || 1), 60000);
            console.log(`🔄 ${rid} reconnecting in ${delay / 1000}s...`);
            reconnectTimers[rid] = (reconnectTimers[rid] || 0) + 1;
            setTimeout(() => startBot(rid, phoneNumber), delay);
        }
    });

    sock.ev.on('creds.update', saveCreds);

    // ---- Incoming messages ----
    sock.ev.on('messages.upsert', async (msg) => {
        const message = msg.messages[0];
        
        if (!message.key || message.key.fromMe) return;
        if (!message.message) return;
        
        const msgId = message.key.id;
        if (msgCache.get(msgId)) return;
        msgCache.set(msgId, true);
        
        const sender = message.key.remoteJid;
        const waId = sender.split('@')[0];
 
        const isButton = !!message.message?.buttonsResponseMessage;
        const buttonData = isButton ? message.message.buttonsResponseMessage : null;
        const callbackData = buttonData?.selectedButtonId || '';
        const buttonText = buttonData?.selectedDisplayText || '';

        const text = message.message.conversation ||
                    message.message.extendedTextMessage?.text ||
                    message.message.imageMessage?.caption ||
                    buttonText ||
                    '';

        const pushName = message.pushName || '';
        const msgType = isButton ? 'buttons_response' : Object.keys(message.message)[0];

        console.log(`📩 [${rid}] ${waId} (${pushName}): ${text.substring(0, 100)} [${msgType}]`);

        await redis.lpush('whatsapp:incoming', JSON.stringify({
            rid: rid,
            wa_id: waId,
            text: text,
            push_name: pushName,
            message_type: msgType,
            callback_data: callbackData,
            timestamp: Date.now(),
        }));
    });

    // ---- Outbound messages ----
    const outboundInterval = setInterval(async () => {
        try {
            const data = await redis.rpop(`whatsapp:outbound:${rid}`);
            if (!data) return;
            
            const msg = JSON.parse(data);
            const jid = `${msg.wa_id}@s.whatsapp.net`;

            if (msg.text) {
                await sock.sendMessage(jid, { text: msg.text });
            }
            
            if (msg.button_text && msg.buttons) {
                await sock.sendMessage(jid, {
                    text: msg.button_text,
                    footer: msg.footer || '',
                    buttons: msg.buttons.map(b => ({
                        buttonId: b.id,
                        buttonText: { displayText: b.text },
                        type: 1,
                    })),
                });
            }
            
            if (msg.image_url) {
                await sock.sendMessage(jid, {
                    image: { url: msg.image_url },
                    caption: msg.caption || '',
                });
            }
            
            console.log(`📤 [${rid}] Sent to ${msg.wa_id}`);
        } catch (err) {
            console.error(`❌ [${rid}] Send error:`, err.message);
        }
    }, 300);

    sock._outboundInterval = outboundInterval;
}

// ---------------------------------------------------------------------------
// Watch Redis for new restaurant registrations
// ---------------------------------------------------------------------------
async function watchForNewRestaurants() {
    const existing = await redis.hgetall('whatsapp:restaurants');
    for (const [rid, phoneNumber] of Object.entries(existing)) {
        if (!sockets[rid]) {
            console.log(`🔌 Starting bot for existing restaurant: ${rid}`);
            startBot(rid, phoneNumber);
        }
    }

    setInterval(async () => {
        try {
            const restaurants = await redis.hgetall('whatsapp:restaurants');
            for (const [rid, phoneNumber] of Object.entries(restaurants)) {
                if (!sockets[rid]) {
                    console.log(`🆕 New restaurant registered: ${rid}`);
                    startBot(rid, phoneNumber);
                }
            }
            
            for (const rid of Object.keys(sockets)) {
                if (!restaurants[rid]) {
                    console.log(`🗑️ Removing stale connection: ${rid}`);
                    sockets[rid].end();
                    delete sockets[rid];
                }
            }
        } catch (err) {
            console.error('❌ Watch error:', err.message);
        }
    }, 5000);
}

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------
import { createServer } from 'http';
createServer((req, res) => {
    if (req.url === '/health') {
        const active = Object.keys(sockets).length;
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok', active_connections: active }));
    } else {
        res.writeHead(404);
        res.end();
    }
}).listen(3000, () => console.log('🏥 Health check on port 3000'));

// ---------------------------------------------------------------------------
// Graceful shutdown
// ---------------------------------------------------------------------------
process.on('SIGTERM', async () => {
    console.log('🛑 Shutting down...');
    for (const [rid, sock] of Object.entries(sockets)) {
        clearInterval(sock._outboundInterval);
        sock.end();
    }
    redis.quit();
    process.exit(0);
});

process.on('SIGINT', async () => {
    console.log('🛑 Interrupted...');
    for (const [rid, sock] of Object.entries(sockets)) {
        clearInterval(sock._outboundInterval);
        sock.end();
    }
    redis.quit();
    process.exit(0);
});

// ---------------------------------------------------------------------------
console.log('🚀 Multi-tenant WhatsApp bot starting...');
watchForNewRestaurants();


// import { makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion, makeCacheableSignalKeyStore } from '@whiskeysockets/baileys';
// import { Redis } from 'ioredis';
// import pino from 'pino';
// import qrcode from 'qrcode-terminal';
// import NodeCache from 'node-cache';

// const logger = pino({ level: 'info' });

// const redis = new Redis({
//     host: process.env.REDIS_HOST || 'redis',
//     port: process.env.REDIS_PORT || 6379,
//     db: 1,
//     retryStrategy: (times) => Math.min(times * 50, 2000),  // Reconnect on failure
//     maxRetriesPerRequest: 3,
// });

// const sockets = {};
// const reconnectTimers = {};  // Track reconnection timers per restaurant
// const msgCache = new NodeCache({ stdTTL: 300 });  // Deduplicate messages (5 min TTL)

// // ---------------------------------------------------------------------------
// // Start bot for a single restaurant
// // ---------------------------------------------------------------------------
// async function startBot(rid, phoneNumber) {
//     // Clear any existing reconnect timer
//     if (reconnectTimers[rid]) {
//         clearTimeout(reconnectTimers[rid]);
//         delete reconnectTimers[rid];
//     }

//     // When a restaurant connects for the first time:

//     // rid is "res8gicp5luoq"

//     // authDir becomes /app/auth/res8gicp5luoq

//     // useMultiFileAuthState creates that folder automatically

//     // After scanning QR code, baileys saves session files inside it
//     const authDir = `/app/auth/${rid}`;
//     const { state, saveCreds } = await useMultiFileAuthState(authDir);
//     const { version } = await fetchLatestBaileysVersion();

//     const sock = makeWASocket({
//         version,
//         auth: state,
//         logger,
//         printQRInTerminal: true,
//         browser: [rid, 'Chrome', '1.0.0'],
//         markOnlineOnConnect: true,
//         syncFullHistory: false,
//     });

//     sockets[rid] = sock;

//     // QR code
//     sock.ev.on('connection.update', (update) => {
//         const { connection, qr, lastDisconnect } = update;
        
//         if (qr) {
//             console.log(`\n📱 Scan QR for ${rid} (${phoneNumber}):`);
//             qrcode.generate(qr, { small: true });
//         }
        
//         if (connection === 'open') {
//             console.log(`✅ ${rid} connected!`);
//             redis.hset('whatsapp:status', rid, 'online');
//         }
        
//         if (connection === 'close') {
//             redis.hset('whatsapp:status', rid, 'offline');
//             delete sockets[rid];
            
//             const statusCode = lastDisconnect?.error?.output?.statusCode;
            
//             if (statusCode === DisconnectReason.loggedOut) {
//                 console.log(`🚫 ${rid} logged out — needs re-scan`);
//                 redis.hset('whatsapp:status', rid, 'logged_out');
//                 return;  // Don't auto-reconnect on logout
//             }
            
//             // Exponential backoff reconnect (max 60 seconds)
//             const delay = Math.min(1000 * Math.pow(2, reconnectTimers[rid] || 1), 60000);
//             console.log(`🔄 ${rid} reconnecting in ${delay / 1000}s...`);
//             reconnectTimers[rid] = (reconnectTimers[rid] || 0) + 1;
//             setTimeout(() => startBot(rid, phoneNumber), delay);
//         }
//     });

//     sock.ev.on('creds.update', saveCreds);

//     // ---- Incoming messages ----
//     sock.ev.on('messages.upsert', async (msg) => {
//         const message = msg.messages[0];
        
//         // Skip own messages, empty messages, and duplicates
//         if (!message.key || message.key.fromMe) return;
//         if (!message.message) return;
        
//         // Deduplicate using message ID
//         const msgId = message.key.id;
//         if (msgCache.get(msgId)) return;
//         msgCache.set(msgId, true);
        
//         const sender = message.key.remoteJid;
//         const waId = sender.split('@')[0];
//         const text = message.message.conversation ||
//                      message.message.extendedTextMessage?.text ||
//                      message.message.imageMessage?.caption ||
//                      '';

//         console.log(`📩 [${rid}] ${waId}: ${text.substring(0, 100)}`);

//         await redis.lpush('whatsapp:incoming', JSON.stringify({
//             rid: rid,
//             wa_id: waId,
//             text: text,
//             message_type: Object.keys(message.message)[0],  // "conversation", "imageMessage", etc.
//             timestamp: Date.now(),
//         }));
//     });

//     // ---- Outbound messages ----
//     const outboundInterval = setInterval(async () => {
//         try {
//             const data = await redis.rpop(`whatsapp:outbound:${rid}`);
//             if (!data) return;
            
//             const msg = JSON.parse(data);
//             const jid = `${msg.wa_id}@s.whatsapp.net`;

//             if (msg.text) {
//                 await sock.sendMessage(jid, { text: msg.text });
//             }
            
//             if (msg.button_text && msg.buttons) {
//                 await sock.sendMessage(jid, {
//                     text: msg.button_text,
//                     footer: msg.footer || '',
//                     buttons: msg.buttons.map(b => ({
//                         buttonId: b.id,
//                         buttonText: { displayText: b.text },
//                         type: 1,
//                     })),
//                 });
//             }
            
//             if (msg.image_url) {
//                 await sock.sendMessage(jid, {
//                     image: { url: msg.image_url },
//                     caption: msg.caption || '',
//                 });
//             }
            
//             console.log(`📤 [${rid}] Sent to ${msg.wa_id}`);
//         } catch (err) {
//             console.error(`❌ [${rid}] Send error:`, err.message);
//         }
//     }, 300);

//     // Store interval reference for cleanup
//     sock._outboundInterval = outboundInterval;
// }

// // ---------------------------------------------------------------------------
// // Watch Redis for new restaurant registrations
// // ---------------------------------------------------------------------------
// async function watchForNewRestaurants() {
//     const existing = await redis.hgetall('whatsapp:restaurants');
//     for (const [rid, phoneNumber] of Object.entries(existing)) {
//         if (!sockets[rid]) {
//             console.log(`🔌 Starting bot for existing restaurant: ${rid}`);
//             startBot(rid, phoneNumber);
//         }
//     }

//     setInterval(async () => {
//         try {
//             const restaurants = await redis.hgetall('whatsapp:restaurants');
//             for (const [rid, phoneNumber] of Object.entries(restaurants)) {
//                 if (!sockets[rid]) {
//                     console.log(`🆕 New restaurant registered: ${rid}`);
//                     startBot(rid, phoneNumber);
//                 }
//             }
            
//             // Clean up connections for restaurants no longer in Redis
//             for (const rid of Object.keys(sockets)) {
//                 if (!restaurants[rid]) {
//                     console.log(`🗑️ Removing stale connection: ${rid}`);
//                     sockets[rid].end();
//                     delete sockets[rid];
//                 }
//             }
//         } catch (err) {
//             console.error('❌ Watch error:', err.message);
//         }
//     }, 5000);
// }

// // ---------------------------------------------------------------------------
// // Health check endpoint (optional)
// // ---------------------------------------------------------------------------
// import { createServer } from 'http';
// createServer((req, res) => {
//     if (req.url === '/health') {
//         const active = Object.keys(sockets).length;
//         res.writeHead(200, { 'Content-Type': 'application/json' });
//         res.end(JSON.stringify({ status: 'ok', active_connections: active }));
//     } else {
//         res.writeHead(404);
//         res.end();
//     }
// }).listen(3000, () => console.log('🏥 Health check on port 3000'));

// // ---------------------------------------------------------------------------
// // Graceful shutdown
// // ---------------------------------------------------------------------------
// process.on('SIGTERM', async () => {
//     console.log('🛑 Shutting down...');
//     for (const [rid, sock] of Object.entries(sockets)) {
//         clearInterval(sock._outboundInterval);
//         sock.end();
//     }
//     redis.quit();
//     process.exit(0);
// });

// process.on('SIGINT', async () => {
//     console.log('🛑 Interrupted...');
//     for (const [rid, sock] of Object.entries(sockets)) {
//         clearInterval(sock._outboundInterval);
//         sock.end();
//     }
//     redis.quit();
//     process.exit(0);
// });

// // ---------------------------------------------------------------------------
// // Start
// // ---------------------------------------------------------------------------
// console.log('🚀 Multi-tenant WhatsApp bot starting...');
// watchForNewRestaurants();