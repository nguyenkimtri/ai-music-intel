const express = require('express');
const { Queue, Worker } = require('bullmq');
const IORedis = require('ioredis');
const multer = require('multer');
const { v4: uuidv4 } = require('uuid');
const Database = require('better-sqlite3');
const path = require('path');
const cors = require('cors');
const fs = require('fs');

const app = express();
const port = process.env.PORT || 8000;

// Setup directories
const uploadsDir = path.join(__dirname, '../uploads');
if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir);

// DB Setup
const db = new Database(path.join(__dirname, '../platform.db'));
db.exec(`
  CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT,
    payload TEXT,
    status TEXT DEFAULT 'pending',
    result TEXT,
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// Redis & Queue Setup
const connection = new IORedis({ maxRetriesPerRequest: null });
const analysisQueue = new Queue('audio-analysis', { connection });

// Multer Storage
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadsDir),
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname);
    cb(null, `${uuidv4()}${ext}`);
  }
});
const upload = multer({ storage });

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../frontend')));

// API: Submit analysis
app.post('/api/analyze', upload.single('audio'), async (req, res) => {
  const { youtube_url } = req.body;
  const jobId = uuidv4();
  let payload = {};

  if (req.file) {
    payload = { type: 'file', path: req.file.path, filename: req.file.originalname };
  } else if (youtube_url) {
    payload = { type: 'youtube', url: youtube_url };
  } else {
    return res.status(400).json({ error: 'No file or URL provided' });
  }

  // Save to DB
  db.prepare('INSERT INTO jobs (id, type, payload) VALUES (?, ?, ?)').run(
    jobId, 
    payload.type, 
    JSON.stringify(payload)
  );

  // Push to BullMQ
  await analysisQueue.add('analyze', { jobId, ...payload });

  res.json({ message: 'Analysis queued', jobId });
});

// API: Check result
app.get('/api/result/:id', (req, res) => {
  const row = db.prepare('SELECT * FROM jobs WHERE id = ?').get(req.params.id);
  if (!row) return res.status(404).json({ error: 'Job not found' });

  res.json({
    id: row.id,
    status: row.status,
    result: row.result ? JSON.parse(row.result) : null,
    error: row.error,
    created_at: row.created_at
  });
});

// API: History
app.get('/api/history', (req, res) => {
  const rows = db.prepare('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 20').all();
  res.json(rows);
});

// BullMQ Event Listeners (Optional: Update status based on BullMQ if needed)
// However, the Python worker will update the SQLite DB directly for simplicity
// or Node will listen for completion. 
// We'll let Python update the DB to minimize Node's CPU usage.

app.listen(port, () => {
  console.log(`Node Server running at http://localhost:${port}`);
});
