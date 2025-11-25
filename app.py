import streamlit as st
import requests
from datetime import datetime
from PIL import Image
import time
import json
from concurrent.futures import ThreadPoolExecutor

# ===============================================
# 1. CONFIGURATION
# ===============================================

# URL Webhook n8n Anda. Pastikan ini benar.
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/chat" 
REQUEST_TIMEOUT = 60 # Timeout request ke n8n (dalam detik)
THREAD_EXECUTOR = ThreadPoolExecutor(max_workers=1) # Executor untuk menjalankan request n8n

# Daftar pesan loading untuk visual feedback
LOADING_MESSAGES = [
    "🧠 Sedang dilakukan analisa pertanyaan...",
    "📚 Menganalisa pustaka jawaban BPR Lestari (RAG)...",
    "📝 Sedang menyusun jawaban dengan Bahasa Indonesia yang santun...",
    "⏱️ Harap menunggu sebentar, jawaban akan segera diberikan...",
]
# Waktu antar pergantian status (misalnya 1 detik untuk tampilan dinamis)
STATUS_CHANGE_INTERVAL = 1 

# ===============================================
# 2. FUNGSI ASINKRON (RUN REQUEST DI THREAD LAIN)
# ===============================================

def run_n8n_request(payload):
    """Fungsi yang akan dijalankan di thread terpisah untuk memanggil n8n."""
    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT
        )
        # Mengembalikan status code dan respons JSON
        return response.status_code, response.json().get("message", "Maaf, terjadi kesalahan pada AI service.")
        
    except requests.exceptions.Timeout:
        return 408, f"Error: Permintaan ke AI Service habis waktu (**Read timed out** setelah {REQUEST_TIMEOUT} detik). Mohon coba lagi atau hubungi Call Center."
    except Exception as e:
        return 500, f"Error koneksi tak terduga: {str(e)}"

# ===============================================
# 3. UI SETUP & INITIALIZATION
# ===============================================

# Custom CSS untuk styling (dihilangkan untuk fokus pada logika utama)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Poppins', sans-serif;
    }
    
    .main-title {
        font-size: 2.5rem !important;
        font-weight: 600 !important;
        color: #1E3A8A !important;
        text-align: center;
        margin-bottom: 0.5rem !important;
    }
    
    .subtitle {
        font-size: 1.2rem !important;
        color: #4B5563 !important;
        text-align: center;
        margin-bottom: 2rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="BPR Lestari AI Assistant", page_icon="💬", layout="wide")

# Logo dan Title
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    try:
        # Ganti 'logo_lestari.png' dengan path file logo Anda
        logo = Image.open("logo_lestari.png") 
        st.image(logo, width=400)
    except FileNotFoundError:
        st.markdown("🏦 [Logo BPR Lestari]")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "user_phone" not in st.session_state:
    st.session_state.user_phone = ""
if "chat_initialized" not in st.session_state:
    st.session_state.chat_initialized = False
# State untuk tracking thread request
if "request_future" not in st.session_state:
    st.session_state.request_future = None
if "request_start_time" not in st.session_state:
    st.session_state.request_start_time = 0

# ===============================================
# 4. INITIALIZATION/ONBOARDING FLOW
# ===============================================

if not st.session_state.chat_initialized:
    # ... (Logika input Nama, No HP, dan Tombol Mulai Chat) ...
    # (Pastikan Anda menyalin logika validasi dari script sebelumnya ke sini)
    
    st.subheader("Selamat Datang! Silakan lengkapi data Anda untuk memulai. 👇")
    st.session_state.user_name = st.text_input("Masukkan **Nama Lengkap** Anda:", value=st.session_state.user_name)
    st.session_state.user_phone = st.text_input("Masukkan **Nomor WhatsApp** Anda (Contoh: 081234567890):", value=st.session_state.user_phone)
    
    if st.button("Mulai Chat"):
        if st.session_state.user_name and st.session_state.user_phone:
            if st.session_state.user_phone.startswith('08') and st.session_state.user_phone.isdigit() and len(st.session_state.user_phone) >= 10:
                st.session_state.chat_initialized = True
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"Halo **{st.session_state.user_name}**, saya Lestari Smart Assistance. Silakan ajukan pertanyaan seputar BPR Lestari. Saya siap membantu."
                })
                st.rerun() 
            else:
                 st.error("Format Nomor WhatsApp tidak valid.")
        else:
            st.error("Nama dan Nomor WhatsApp wajib diisi untuk memulai chat.")
    
    st.stop() 

# ===============================================
# 5. CHAT INTERFACE & LOGIC (ASYNCHRONOUS)
# ===============================================

# 5.1. Cek Hasil Request yang Sedang Berjalan
if st.session_state.request_future is not None:
    
    future = st.session_state.request_future
    
    with st.chat_message("assistant"):
        
        # Cek apakah request sudah selesai
        if future.done():
            # Jika selesai, ambil hasil, tampilkan, dan reset state
            status_code, ai_response = future.result()
            
            # Hapus placeholder loading
            st.session_state.loading_placeholder.empty()

            # Tampilkan respons
            st.markdown(ai_response)
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            
            # Reset state request
            st.session_state.request_future = None
            st.session_state.request_start_time = 0
            
            st.rerun() # Rerun untuk menghilangkan status loading
            
        else:
            # Jika belum selesai, tampilkan progress bar dan pesan loading dinamis
            
            # Dapatkan placeholder dari state
            message_placeholder = st.session_state.loading_placeholder
            start_time = st.session_state.request_start_time
            
            elapsed_time = time.time() - start_time
            
            # --- LOGIKA LAMA (LOOPING) ---
            # message_index = int(elapsed_time // STATUS_CHANGE_INTERVAL) % len(LOADING_MESSAGES)
            
            # --- LOGIKA BARU (MAJU SATU KALI DAN BERHENTI) ---
            max_index = len(LOADING_MESSAGES) - 1
            # Hitung indeks berdasarkan waktu yang berlalu (tapi tidak boleh melebihi indeks maksimal)
            message_index = min(int(elapsed_time // STATUS_CHANGE_INTERVAL), max_index)
            
            current_message = LOADING_MESSAGES[message_index]
            
            # Simulasikan Progress Bar (Maksimal 90% saat menunggu)
            progress_val = min(int(elapsed_time / REQUEST_TIMEOUT * 100 * 0.9), 90)

            message_placeholder.progress(progress_val, text=current_message)
            
            # Penting: St.rerun() agar Streamlit terus memperbarui tampilan (loop)
            time.sleep(3) # Jeda kecil agar Streamlit tidak terlalu berat
            st.rerun()


# 5.2. Tampilkan pesan chat yang sudah ada
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5.3. Handle Chat Input
if prompt := st.chat_input("Apa pertanyaan Anda?", disabled=st.session_state.request_future is not None):
    
    # Tambahkan pesan user ke history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Siapkan Payload
    payload = {
        "message": prompt,
        "user_name": st.session_state.user_name, 
        "user_phone": st.session_state.user_phone, 
        "timestamp": datetime.now().isoformat()
    }

    # Buat placeholder untuk loading message
    with st.chat_message("assistant"):
        st.session_state.loading_placeholder = st.empty()
        
    # Kirim request ke thread terpisah
    st.session_state.request_future = THREAD_EXECUTOR.submit(run_n8n_request, payload)
    st.session_state.request_start_time = time.time()
    
    # Rerun untuk masuk ke loop cek hasil request (Bagian 5.1)
    st.rerun()