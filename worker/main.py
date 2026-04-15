import asyncio
import os
import json
import sqlite3
import librosa
import numpy as np
import yt_dlp
from bullmq import Worker

# Profiles for Key Detection
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

DB_PATH = os.path.join(os.path.dirname(__file__), "../platform.db")

def update_db(job_id, status, result=None, error=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if result:
        cursor.execute("UPDATE jobs SET status=?, result=? WHERE id=?", (status, json.dumps(result), job_id))
    elif error:
        cursor.execute("UPDATE jobs SET status=?, error=? WHERE id=?", (status, error, job_id))
    else:
        cursor.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
    conn.commit()
    conn.close()

def detect_key(y, sr):
    y_harmonic = librosa.effects.hpss(y)[0]
    chromagram = librosa.feature.chroma_stft(y=y_harmonic, sr=sr)
    mean_chroma = np.mean(chromagram, axis=1)
    
    correlations = []
    for i in range(12):
        major_rotated = np.roll(MAJOR_PROFILE, i)
        minor_rotated = np.roll(MINOR_PROFILE, i)
        major_corr = np.corrcoef(mean_chroma, major_rotated)[0, 1]
        minor_corr = np.corrcoef(mean_chroma, minor_rotated)[0, 1]
        correlations.append((major_corr, f"{NOTES[i]} Major", "major"))
        correlations.append((minor_corr, f"{NOTES[i]} Minor", "minor"))
    
    best_match = max(correlations, key=lambda x: x[0])
    return {"key": best_match[1], "scale": best_match[2]}

def download_youtube(url, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    temp_name = os.path.join(output_dir, f"yt_{np.random.randint(1000, 9999)}")
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': temp_name + '.%(ext)s',
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
        return temp_name + '.mp3'

async def process_job(job, token):
    data = job.data
    job_id = data.get("jobId")
    print(f"Processing job {job_id}...")
    
    update_db(job_id, "processing")
    
    try:
        file_path = ""
        if data["type"] == "youtube":
            file_path = download_youtube(data["url"], os.path.join(os.path.dirname(__file__), "../uploads/youtube"))
        else:
            file_path = data["path"]
            
        # Analysis
        y, sr = librosa.load(file_path, sr=22050, mono=True)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        key_info = detect_key(y, sr)
        
        result = {
            "key": key_info["key"],
            "bpm": round(float(tempo), 1),
            "scale": key_info["scale"]
        }
        
        update_db(job_id, "completed", result=result)
        print(f"Job {job_id} completed successfully.")
        
        # Cleanup YT temp file
        if data["type"] == "youtube" and os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        print(f"Error processing job {job_id}: {e}")
        update_db(job_id, "failed", error=str(e))

async def main():
    redis_url = "redis://localhost:6379"
    print("Worker starting...")
    worker = Worker("audio-analysis", process_job, {"connection": redis_url})
    
    # Run until keyboard interrupt
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        print("Worker stopping...")
        await worker.close()

if __name__ == "__main__":
    asyncio.run(main())
