# Serverga joylashtirish

## Holat (2026-11-07)

Server: `mastersat.uz` turgan mashina, `65.109.100.104`, Ubuntu 24.04.

**Bajarilgan:**

- `chiztop` tizim foydalanuvchisi va `/opt/chiztop`
- kod, virtual muhit, bog'liqliklar
- `/etc/chiztop.env` (chmod 600) — **token hali bo'sh**
- `chiztop.service` — ishlayapti, avtoyuklanishga qo'yilgan
- nginx sayti `chiz.mastersat.uz` uchun (hozircha faqat HTTP)
- `http://127.0.0.1:8077/health` javob beryapti

Mavjud saytlar tekshirildi va buzilmagan: mastersat.uz va uning barcha
subdomenlari ishlayapti.

**Qolgan uchta qadam — pastda, "Nima qolgan" bo'limida.**

---

Mo'ljallangan server: `mastersat.uz` turgan mashina (`65.109.100.104`).
Unda nginx allaqachon ishlayapti, shuning uchun o'yin yoniga qo'shiladi,
mavjud saytlarga tegilmaydi.

## 0. Sizdan talab qilinadigan ikki narsa

**DNS yozuvi.** `chiz.mastersat.uz` uchun A yozuvi `65.109.100.104` ga
yo'naltirilishi kerak. Buni domen boshqaruv panelingizda o'zingiz
qilasiz — DNS tarqalgunicha certbot sertifikat ololmaydi.

**Bo'sh port.** Quyidagi qadamlar 8077 ni ishlatadi. Band bo'lsa
tekshiring va o'zgartiring:

```bash
ss -lntp | grep 8077
```

## 1. Foydalanuvchi va papka

```bash
sudo useradd --system --home /opt/chiztop --shell /usr/sbin/nologin chiztop
sudo mkdir -p /opt/chiztop && sudo chown chiztop:chiztop /opt/chiztop
```

## 2. Kodni yuborish

```bash
rsync -az --exclude '.git' --exclude '.venv' --exclude '.pytest_cache' \
      ./ root@65.109.100.104:/opt/chiztop/
```

## 3. Virtual muhit

```bash
sudo -u chiztop python3 -m venv /opt/chiztop/.venv
sudo -u chiztop /opt/chiztop/.venv/bin/pip install -r /opt/chiztop/requirements.txt
```

## 4. Token

```bash
sudo cp deploy/chiztop.env.example /etc/chiztop.env
sudo nano /etc/chiztop.env          # BOT_TOKEN ni qo'ying
sudo chmod 600 /etc/chiztop.env
```

`CHIZTOP_DEV` ni bu yerga **yozmang**. U imzo tekshiruvini o'chiradi.

## 5. Xizmat

```bash
sudo cp deploy/chiztop.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now chiztop
systemctl status chiztop --no-pager
curl -sf http://127.0.0.1:8077/health && echo OK
```

## 6. Nginx va sertifikat

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/chiztop
sudo ln -s /etc/nginx/sites-available/chiztop /etc/nginx/sites-enabled/
sudo nginx -t                        # mavjud saytlarni buzmaganini tekshiradi
sudo systemctl reload nginx
sudo certbot --nginx -d chiz.mastersat.uz
```

`nginx -t` xato bersa, symlink'ni o'chiring va qayta yuklang — boshqa
saytlar ishlashda davom etadi.

## 7. Telegram

1. [@BotFather](https://t.me/BotFather) → `/newbot` → tokenni
   `/etc/chiztop.env` ga qo'ying
2. `/newapp` → URL: `https://chiz.mastersat.uz`
3. `web/app.js` dagi `APP_LINK` ni to'ldiring:
   ```js
   const APP_LINK = "https://t.me/sizning_bot/play";
   ```
4. Qayta yuboring: `./deploy/deploy.sh root@65.109.100.104`

## 8. Tekshirish

```bash
curl -sf https://chiz.mastersat.uz/health
```

Keyin botdan mini-appni oching, "Yangi o'yin" bosing va havolani
o'zingizga yuboring — ikkinchi qurilmadan kirib ko'ring.

## Keyingi yangilanishlar

```bash
./deploy/deploy.sh root@65.109.100.104
```

## Loglar

```bash
sudo journalctl -u chiztop -f
```

## Muhim cheklov

Xonalar jarayon xotirasida yashaydi. Shuning uchun `--workers 1` shart va
xizmatni qayta ishga tushirish o'ynalayotgan o'yinlarni uzadi. Yangilashni
odamlar o'ynamaydigan vaqtda qiling.


---

## Nima qolgan

### 1. DNS yozuvi (faqat siz qila olasiz)

Domen panelida:

```
chiz    A    65.109.100.104
```

Tarqalganini tekshiring:

```bash
dig +short chiz.mastersat.uz
```

### 2. Bot tokeni

@BotFather da bot yarating, keyin serverda:

```bash
ssh root@65.109.100.104 'nano /etc/chiztop.env'   # BOT_TOKEN=... qo'ying
ssh root@65.109.100.104 'systemctl restart chiztop'
```

Token bo'sh turganda server ishlaydi, lekin hech kim o'yinga kira olmaydi:
har bir ulanish imzo tekshiruvida rad etiladi.

### 3. Sertifikat (DNS tarqalgandan keyin)

```bash
ssh root@65.109.100.104 'certbot --nginx -d chiz.mastersat.uz'
```

Certbot nginx konfiguratsiyasiga TLS blokini o'zi qo'shadi.

### 4. Mini-appni ulash

@BotFather → `/newapp` → URL: `https://chiz.mastersat.uz`

Keyin `web/app.js` dagi `APP_LINK` ni to'ldiring va qayta yuboring:

```bash
./deploy/deploy.sh root@65.109.100.104
```
