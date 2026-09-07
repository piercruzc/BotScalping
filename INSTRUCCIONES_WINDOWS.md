# BotScalping — Guía Windows (Vantage MT5 + Telegram)

Instrucciones para instalar, configurar y usar el bot en una **máquina Windows**. El paquete oficial `MetaTrader5` **no funciona en Mac**. En Mac solo puedes editar código y pasar tests; las órdenes salen únicamente desde Windows con MT5 abierto.

El bot:

- Lee señales XAUUSD del canal VIP de Telegram (tu cuenta de usuario, no un bot de canal).
- Arma **3 entradas con el mismo lotaje** (market, limit o stop según el precio en vivo).
- Las envía al **MT5 de Vantage**.
- Muestra un panel en `http://127.0.0.1:8787` para modo Demo/Real, lotaje y parámetros.
- **Pegar una señal a mano solo existe en Demo.** En Real solo opera el canal de Telegram.

---

## Después de clonar el repo (Windows)

Ya tienes el código. En **PowerShell** o **CMD**, entra a la carpeta del clone (ajusta la ruta):

```bat
cd C:\Users\TuUsuario\Documents\BotScalping
```

### Primera vez en esa PC

Hace falta Python 64-bit 3.10–3.12 y MT5 de Vantage instalados (secciones 2.1 y 2.2). En MT5, una vez: trading algorítmico + botón Algo Trading **verde** + oro en Market Watch (sección 2.2.1).

```bat
python --version
python -c "import struct; print(struct.calcsize('P') * 8)"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

En `.env` rellena Telegram (`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_CHANNEL_ID`) y, si no vas a abrir MT5 a mano, `MT5_PATH` + `MT5_DEMO_LOGIN` / `PASSWORD` / `SERVER`. Detalle en las secciones 4 y 5.

Si no estás seguro del ID del canal:

```bat
python -m src.list_chats
```

Copia el `TELEGRAM_CHANNEL_ID` de la línea `[CANAL]` del VIP al `.env`. Luego:

```bat
python -m src
```

La primera vez Telethon pide teléfono, código y 2FA si la tienes. Cuando la consola diga que el panel está listo:

1. Abre [http://127.0.0.1:8787](http://127.0.0.1:8787)
2. Revisa que MT5 figure conectado (DEMO).
3. Deja **Demo** y **dry-run** al principio.

### Las siguientes veces (ya instalado y con `.env`)

```bat
cd C:\Users\TuUsuario\Documents\BotScalping
python -m src
```

- Si `MT5_PATH` + credenciales están en `.env`, no hace falta abrir MT5 a mano.
- Si `MT5_PATH` está vacío, abre MT5, loguea y deja Algo Trading en verde **antes** de `python -m src`.
- Panel: [http://127.0.0.1:8787](http://127.0.0.1:8787)
- Parar: `Ctrl+C` en la consola.

No vuelvas a clonar ni a `pip install` cada día, salvo que cambien las dependencias.

---

## 1. Qué necesitas tener antes

- Windows 10 u 11 **64-bit**.
- Cuenta **demo** de Vantage (después, si quieres, la real).
- Acceso al canal VIP de Telegram **con la misma cuenta** que usarás en el bot (tienes que ser miembro).
- Este proyecto copiado a la PC (USB, OneDrive, git, etc.). Ejemplo: `C:\Users\TuUsuario\Documents\BotScalping`
- La PC **no debe dormir** mientras el bot opera. Oro cotiza casi 24/5.

---

## 2. Programas a instalar

Instala en este orden.

### 2.1 Python 64-bit (3.10, 3.11 o 3.12)

1. Entra a [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/).
2. Descarga el instalador **Windows installer (64-bit)**. No uses 32-bit: el paquete MetaTrader5 no instala bien.
3. Al instalar, marca **Add python.exe to PATH**.
4. Abre **Símbolo del sistema** o **PowerShell** y comprueba:

```bat
python --version
python -c "import struct; print(struct.calcsize('P') * 8)"
```

Debe salir `3.10` / `3.11` / `3.12` y **`64`**.

Si `python` no se reconoce, cierra y abre la terminal, o usa `py -3.12`.

### 2.2 MetaTrader 5 de Vantage

1. Entra a Vantage → Platforms → MetaTrader 5 y descarga el terminal de **Vantage** (no el MT5 genérico de otro broker).
2. Instálalo y ábrelo **al menos una vez** (aunque luego uses solo el path).
3. Inicia sesión con la cuenta **demo**.
4. En Market Watch (Ctrl+M) busca el oro. El nombre puede ser `XAUUSD`, `GOLD` o `XAUUSDm`. Anótalo; tiene que coincidir con el símbolo del panel.
5. Activa lo de la sección **2.2.1** (si no lo haces, el bot conecta pero no envía órdenes).
6. Anota la ruta de `terminal64.exe` (acceso directo de MT5 → Propiedades → Destino). Ejemplo:
   `C:\Program Files\Vantage MetaTrader 5\terminal64.exe`

No hace falta poner un Expert Advisor en el gráfico. El bot usa la API de Python, no un `.ex5`.

### 2.2.1 Qué activar en MT5 (una sola vez)

Estas opciones quedan guardadas en el terminal. El path **no** las enciende por ti.

1. **Herramientas → Opciones → Asesores Expertos** (Expert Advisors):
   - Marca **Permitir trading algorítmico** (Allow algorithmic trading).
2. En la barra de herramientas, el botón **Algo Trading** / **AutoTrading** debe quedar **verde**. Si está rojo, Python no puede mandar órdenes.
3. El oro visible en Market Watch.
4. Opcional: al loguear, marca **guardar contraseña** (por si algún día no pones las credenciales en `.env`).

### 2.2.2 ¿Abrir MT5 a mano o solo el path?

Hay dos formas. Las dos necesitan que hayas hecho el 2.2.1 **una vez**.

**A — Abres MT5 tú**  
Deja `MT5_PATH` vacío. El terminal ya logueado es suficiente. El bot se engancha al que esté abierto.

**B — No abres MT5; solo pones el path**  
`initialize` puede **arrancar** el terminal solo. En `.env` pon la ruta **y** usuario/contraseña/servidor. El path solo abre el programa; sin credenciales usará la última sesión guardada, y si no hay ninguna, se abre y el bot no conecta.

```env
MT5_PATH=C:\Program Files\Vantage MetaTrader 5\terminal64.exe
MT5_DEMO_LOGIN=123456
MT5_DEMO_PASSWORD=tu_password
MT5_DEMO_SERVER=VantageInternational-Demo
```

- Path = “abre este MT5” (el de Vantage, no el de otro broker).
- Credenciales = “entra a esta cuenta”.
- Trading algorítmico + botón verde = “autoriza órdenes”.

### 2.3 (Opcional) Git

Solo si quieres clonar o actualizar el repo. [https://git-scm.com/download/win](https://git-scm.com/download/win)

### 2.4 Navegador

Cualquiera. El panel es local: `http://127.0.0.1:8787`

No hace falta Node.js, Docker ni Visual Studio.

---

## 3. Dependencias de Python

Abre PowerShell o CMD, entra a la carpeta del proyecto:

```bat
cd C:\Users\TuUsuario\Documents\BotScalping
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Eso instala:

| Paquete        | Para qué                                      |
|----------------|-----------------------------------------------|
| MetaTrader5    | API oficial al terminal MT5 (solo Windows)    |
| telethon       | Leer el canal de Telegram con tu usuario      |
| fastapi        | Panel web                                     |
| uvicorn        | Servidor del panel                            |
| pyyaml         | `config.yaml`                                 |
| python-dotenv  | Leer `.env`                                   |
| pytest         | Tests (opcional en el día a día)              |

Comprueba que MetaTrader5 cargó:

```bat
python -c "import MetaTrader5 as mt5; print(mt5.__version__)"
```

Si falla, casi siempre es Python 32-bit o no estás en Windows.

Tests (opcionales):

```bat
python -m pytest -q
```

---

## 4. Telegram: API y canal

El bot **no es un bot de Telegram**. Usa **tu cuenta** (Telethon). Un bot oficial no puede leer un canal donde no eres admin.

### 4.1 API ID y API Hash

1. Entra a [https://my.telegram.org](https://my.telegram.org) con el **mismo número** del canal VIP.
2. Ve a **API development tools**.
3. Crea una app (el nombre da igual, ej. `BotScalping`).
4. Copia **api_id** (número) y **api_hash** (texto).

### 4.2 ID del canal de señales (`TELEGRAM_CHANNEL_ID`)

El bot solo lee el canal que pongas aquí. No lo descubre solo.

**Canal público** (tiene @usuario):

```
TELEGRAM_CHANNEL_ID=@nombre_del_canal
```

**Canal privado / VIP** (lo habitual): ID numérico, casi siempre con `-100` delante.

**La forma más segura** (con `.env` ya teniendo `TELEGRAM_API_ID` y `TELEGRAM_API_HASH`):

```bat
python -m src.list_chats
```

En la lista busca la línea `[CANAL]` del VIP y copia `TELEGRAM_CHANNEL_ID=...` (empieza por `-100`). **No uses un id de `[usuario]`**. Eso provoca el error `PeerUser` / *Could not find the input entity*.

Otras formas:

1. Telegram Web: entra al VIP y mira la URL (`#-1001234567890`).
2. Reenvía un mensaje del **canal** (no un chat privado) a [@userinfobot](https://t.me/userinfobot) o [@getidsbot](https://t.me/getidsbot).

`NOTIFY_CHAT_ID` es tu usuario (número positivo). No lo pongas en `TELEGRAM_CHANNEL_ID`.

Tienes que ser **miembro** de ese canal con la misma cuenta del login de Telethon.

### 4.3 Chat para avisos (`NOTIFY_CHAT_ID`)

Es **tu** usuario, no el canal. Ahí el bot te escribe si aceptó o rechazó una señal.

- Escríbete a ti mismo o a [@userinfobot](https://t.me/userinfobot) y copia tu user id (número positivo).
- Si no lo pones, el bot funciona igual; solo no te manda esos avisos.

---

## 5. Archivo `.env`

En la raíz del proyecto:

```bat
copy .env.example .env
```

Ábrelo con el Bloc de notas y rellena (sin comillas):

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef0123456789
TELEGRAM_CHANNEL_ID=-1001234567890
NOTIFY_CHAT_ID=123456789

MT5_PATH=

MT5_DEMO_LOGIN=123456
MT5_DEMO_PASSWORD=tu_password_demo
MT5_DEMO_SERVER=VantageInternational-Demo

MT5_LIVE_LOGIN=
MT5_LIVE_PASSWORD=
MT5_LIVE_SERVER=
```

Notas:

- `MT5_PATH` vacío = debes tener MT5 abierto y logueado.
- `MT5_PATH` con la ruta a `terminal64.exe` = el bot puede **abrir MT5 solo**. Pon también `MT5_DEMO_*` (y `MT5_LIVE_*` si usarás real). La ruta la sacas del acceso directo → Propiedades → Destino.
- El **nombre exacto del servidor** lo ves en MT5 al iniciar sesión (no lo inventes).
- Si el terminal ya está logueado, el bot puede conectar sin login/password. Las credenciales hacen falta para arrancar por path y para que el switch Demo/Real intente cambiar de cuenta.
- **No subas `.env` a git** ni lo compartas. Ahí van contraseñas y la sesión de Telegram.

---

## 6. Primer arranque

1. Primera vez: abre **MT5 Vantage**, activa lo del **2.2.1** (algorítmico + botón verde + oro en Market Watch) y cierra si quieres usar solo el path.
2. Cada sesión: o dejas MT5 abierto, **o** tienes `MT5_PATH` + `MT5_DEMO_*` en `.env` para que el bot lo abra.
3. En PowerShell, desde la carpeta del proyecto:

```bat
cd C:\Users\TuUsuario\Documents\BotScalping
python -m src
```

4. La **primera vez** Telethon pide en la consola:
   - Número de teléfono con código de país (`+51...`, `+52...`, etc.).
   - Código que Telegram te manda.
   - Contraseña 2FA si la tienes.
5. Se crea `sessions/piply.session`. No la borres ni la copies a otro PC sin cuidado: es tu login de Telegram.
6. Cuando veas algo como `Panel en http://127.0.0.1:8787` y `Telegram conectado`, abre esa URL en el navegador.

Para parar: `Ctrl+C` en la consola. Cerrar el navegador **no** para el bot.

---

## 7. Cómo usar el panel

Dirección fija: [http://127.0.0.1:8787](http://127.0.0.1:8787)

Al arrancar siempre está en **Demo**. Dry-run suele venir **activado** (planea órdenes, no las manda).

### 7.1 Qué puedes cambiar

- **Lotaje**: un solo número. Las 3 entradas usan exactamente ese lote (ej. `0.01` → tres tickets de `0.01`).
- Símbolo (el de Market Watch).
- Tamaño de pip (en oro suele ser `0.1`: 80 pips ≈ 8.00 de precio).
- Spread máximo, tolerancia de entrada, buffer de no perseguir.
- Colchón de break even, deviation, trail TP4.
- Telegram ON/OFF **solo en Demo**. En Real Telegram queda forzado encendido.
- Dry-run.

Pulsa **Guardar parámetros**. Se escriben en `config.yaml` sin reiniciar.

### 7.2 Demo

1. Switch **Demo**.
2. La cuenta MT5 tiene que ser demo. Si el terminal está en real, el bot **bloquea** órdenes.
3. Quita dry-run cuando quieras que mande de verdad a la demo.
4. **Pegar señal**: pega el texto del canal → **Previsualizar** (ves limit/stop/market de las 3 patas) → **Ejecutar en demo**.
5. También puedes dejar Telegram ON y esperar una señal real del canal (sigue siendo cuenta demo).

### 7.3 Real

1. En MT5 inicia sesión en la cuenta **live** (o completa `MT5_LIVE_*` en `.env` y cambia el switch para que intente reconectar).
2. En el panel: **Real** → escribe `REAL` → confirmar.
3. Desaparece pegar/ejecutar a mano. **Solo el canal de Telegram** abre órdenes.
4. El lotaje y el resto de parámetros se siguen cambiando en el panel.
5. Si el switch dice Real pero MT5 sigue en demo (o al revés), **no opera**.

Para volver a Demo: un clic en **Demo**. Se anula la confirmación REAL.

---

## 8. Cómo opera una señal

Formato que entiende (los precios cambian; la estructura no):

```
📌BUY : XAUUSD “SCALP”
FIRST ENTRY : 4411
SECOND ENTRY : 4407
↗️ TP1: 4415
↗️ TP2: 4420
↗️ TP3: 4430
↗️ Tp4 : Trail SL to maximize profits.
‼️SL: 4403 (80 pips)
```

También el formato del PDF (Entrada 1 / Entrada 2).

Reglas:

- 3 tickets: FIRST → TP1, punto medio → TP2, SECOND → TP3 (o trail si está activo).
- Mismo lotaje en las tres.
- BUY: ask ≈ entrada → market; ask por encima → buy limit; ask por debajo → buy stop. SELL al revés.
- Si el precio ya pasó TP1, descarta la señal (no persigue).
- Spread demasiado alto → no envía.
- Al tocar TP1, mueve el SL de lo que quede a **break even del precio medio**.
- Una sola señal activa a la vez (posiciones/pendientes del magic `260907`).

---

## 9. Uso del día a día

1. Encender Windows (que no duerma).
2. Si usas **path + credenciales**, no hace falta abrir MT5 a mano. Si `MT5_PATH` está vacío, abre MT5 y loguea.
3. `python -m src` en la carpeta del proyecto.
4. Abrir `http://127.0.0.1:8787` y revisar: cuenta DEMO/REAL, bid/ask, modo, dry-run.
5. Dejar la consola abierta. Si el bot arrancó MT5, no lo cierres.

Opcional: tarea programada al iniciar Windows con `python -m src` (con path y credenciales en `.env` no necesitas abrir MT5 antes).

---

## 10. Archivos importantes

| Archivo / carpeta        | Qué es                                      | ¿Se comparte? |
|--------------------------|---------------------------------------------|---------------|
| `.env`                   | Secretos Telegram + logins MT5              | No            |
| `config.yaml`            | Lotaje, modo, trail, puerto del panel       | Sí (sin secretos) |
| `sessions/piply.session` | Login de tu Telegram                        | No            |
| `state.json`             | Señales ya procesadas y señal activa        | No hace falta |
| `src/`                   | Código                                      | Sí            |

---

## 11. Problemas frecuentes

**`Telegram no configurado`**  
Falta `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` o `TELEGRAM_CHANNEL_ID` en `.env`. El archivo debe llamarse exactamente `.env` y estar en la raíz del proyecto.

**`Could not find the input entity for PeerUser` / no sale “Telegram conectado”**  
Pusiste un ID de **usuario** (el tuyo o el de un bot) en `TELEGRAM_CHANNEL_ID`. Para: `python -m src.list_chats`, copia el id de la línea `[CANAL]` del VIP (con `-100`) al `.env`, reinicia `python -m src`. En el panel, la tarjeta Telegram debe decir el **nombre del canal**.

**No llegan señales del canal**  
- ID del canal incorrecto (prueba `list_chats` o Telegram Web con `-100`).  
- No eres miembro, o logueaste otra cuenta en Telethon.  
- Borra `sessions/` solo si quieres reloguear (te pedirá el teléfono otra vez).  
- El canal tiene que enviar texto con BUY/SELL, entries, TPs y SL. Si no parsea, no opera (y no marca error si el mensaje no parece señal).

**`El paquete MetaTrader5 solo funciona en Windows`**  
Estás en Mac/Linux, o Python no cargó el paquete.

**MT5 no conecta**  
- Sin path: el terminal tiene que estar abierto y logueado.  
- Con path: revisa que sea el `terminal64.exe` de Vantage y que `MT5_DEMO_LOGIN` / `PASSWORD` / `SERVER` sean correctos. El path solo no loguea si no hay sesión guardada.  
- Trading algorítmico desactivado o botón Algo Trading en rojo: el bot no envía órdenes. Actívalo una vez (sección 2.2.1).

**Switch Demo + cuenta REAL (o al revés)**  
El candado bloquea a propósito. Alinea el login de MT5 con el switch.

**Símbolo no encontrado**  
Cambia `symbol` en el panel al nombre exacto de Market Watch (`XAUUSD` / `GOLD` / `XAUUSDm`).

**Órdenes en dry-run no aparecen en MT5**  
Es normal. Dry-run solo muestra el plan. Quítalo para enviar.

**Python no es 64-bit**  
Desinstala Python 32-bit, instala 64-bit, `pip install -r requirements.txt` otra vez.

**La PC se durmió y perdiste señales**  
Windows → Configuración → Sistema → Energía → nunca suspender mientras está enchufada. Para 24/5, un VPS Windows con el mismo proyecto.

---

## 12. Pasar de demo a real (checklist)

1. Probaste pegar señal y una señal real del canal en **demo**, sin dry-run, y viste 3 tickets en MT5.
2. El lotaje del panel es el que quieres usar con dinero real.
3. Login live en MT5 Vantage.
4. Switch **Real**, escribes `REAL`.
5. Confirmas en el panel que el badge de cuenta dice REAL y no hay error de alineación.
6. Dry-run **apagado**.
7. No se pega nada a mano. Solo el canal.

El bot replica la señal. No garantiza beneficio. Empieza con el lote más pequeño que Vantage permita.

---

## 13. Resumen rápido

```bat
:: Una sola vez
python --version
python -m pip install -r requirements.txt
copy .env.example .env
:: edita .env (Telegram + canal + MT5)

:: Cada sesión
:: Con MT5_PATH + credenciales el bot abre MT5 solo
:: Si no hay path: abre MT5 a mano (botón Algo Trading verde)
python -m src
:: Navegador: http://127.0.0.1:8787
```
