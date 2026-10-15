# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["mlx-whisper", "sounddevice", "numpy", "pyobjc-framework-Cocoa", "pyobjc-framework-Quartz"]
# ///
"""Dictado: alternativa gratuita y 100% local a Wispr Flow para Mac Apple Silicon.

- Mantén pulsada la combinación (Ctrl + Option por defecto) y habla; al soltar se pega el texto.
- Pulsación corta: la grabación queda "bloqueada"; púlsala otra vez para terminar.
- Widget flotante con onda de voz, icono en la barra de menú, diccionario propio.

Uso:  uv run --python 3.12 dictado.py
      uv run --python 3.12 dictado.py --instalar     (arranque automático al iniciar sesión)
      uv run --python 3.12 dictado.py --desinstalar
"""
import json
import math
import os
import plistlib
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

HOME = Path.home()
CFG_DIR = HOME / ".dictado"
CFG_FILE = CFG_DIR / "config.json"
DICT_FILE = CFG_DIR / "diccionario.txt"
LOG_FILE = CFG_DIR / "historial.txt"
AGENT = HOME / "Library/LaunchAgents/com.dictado.app.plist"
MODEL = os.environ.get("DICTADO_MODEL", "mlx-community/whisper-large-v3-turbo")
SAMPLE_RATE = 16000
TAP_MAX = 0.35  # pulsación más corta que esto = grabación bloqueada


def install() -> None:
    dest = HOME / "Dictado"
    dest.mkdir(exist_ok=True)
    if Path(__file__).resolve() != (dest / "dictado.py").resolve():
        shutil.copy(__file__, dest / "dictado.py")
    uv = shutil.which("uv") or str(HOME / ".local/bin/uv")
    if not Path(uv).exists():
        raise SystemExit(
            "No se encontro uv. Instalalo desde https://docs.astral.sh/uv/ y vuelve a intentarlo."
        )
    py = dest / "venv/bin/python"
    if not py.exists():
        subprocess.run([uv, "venv", "--python", "3.12", str(dest / "venv")], check=True)
        subprocess.run(
            [uv, "pip", "install", "--python", str(py), "mlx-whisper", "sounddevice", "numpy",
             "pyobjc-framework-Cocoa", "pyobjc-framework-Quartz"],
            check=True,
        )
    app = HOME / "Applications/Dictado.app"
    (app / "Contents/MacOS").mkdir(parents=True, exist_ok=True)
    (app / "Contents/Info.plist").write_bytes(plistlib.dumps({
        "CFBundleName": "Dictado",
        "CFBundleDisplayName": "Dictado",
        "CFBundleIdentifier": "com.dictado.app",
        "CFBundleExecutable": "dictado-launcher",
        "CFBundlePackageType": "APPL",
        "CFBundleVersion": "1",
        "LSUIElement": True,
        "NSMicrophoneUsageDescription": "Dictado necesita el micrófono para transcribir lo que dices.",
    }))
    # Lanzador nativo: la app (no Python) es el proceso responsable de los permisos de macOS
    csrc = dest / "launcher.c"
    csrc.write_text(f"""
#include <spawn.h>
#include <signal.h>
#include <sys/wait.h>
#include <fcntl.h>
extern char **environ;
static pid_t child;
static void fwd(int s) {{ if (child > 0) kill(child, s); }}
int main(void) {{
    signal(SIGTERM, fwd); signal(SIGINT, fwd);
    posix_spawn_file_actions_t fa; posix_spawn_file_actions_init(&fa);
    posix_spawn_file_actions_addopen(&fa, 1, "{dest / 'dictado.log'}", O_WRONLY | O_CREAT | O_APPEND, 0644);
    posix_spawn_file_actions_adddup2(&fa, 1, 2);
    char *args[] = {{"{py}", "{dest / 'dictado.py'}", 0}};
    if (posix_spawn(&child, "{py}", &fa, 0, args, environ) != 0) return 1;
    int st; waitpid(child, &st, 0); return 0;
}}
""")
    launcher = app / "Contents/MacOS/dictado-launcher"
    subprocess.run(["clang", "-O1", "-o", str(launcher), str(csrc)], check=True)
    subprocess.run(["codesign", "--force", "--deep", "-s", "-", str(app)], capture_output=True)
    plist = {
        "Label": "com.dictado.app",
        "ProgramArguments": ["/usr/bin/open", str(app)],
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(dest / "dictado.log"),
        "StandardErrorPath": str(dest / "dictado.log"),
        "EnvironmentVariables": {
            "PATH": f"/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:{HOME}/.local/bin"
        },
    }
    AGENT.parent.mkdir(exist_ok=True)
    AGENT.write_bytes(plistlib.dumps(plist))
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(AGENT)], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(AGENT)])
    print(f"Instalado: {app}. Arrancará solo al iniciar sesión.")


def uninstall() -> None:
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(AGENT)], capture_output=True)
    AGENT.unlink(missing_ok=True)
    print("Arranque automático desactivado (la carpeta ~/Dictado se conserva).")


if "--instalar" in sys.argv:
    install()
    sys.exit(0)
if "--desinstalar" in sys.argv:
    uninstall()
    sys.exit(0)

import numpy as np  # noqa: E402
import objc  # noqa: E402
import sounddevice as sd  # noqa: E402
from AppKit import (  # noqa: E402
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSEvent,
    NSEventMaskFlagsChanged,
    NSImage,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSPanel,
    NSScreen,
    NSStatusBar,
    NSStatusWindowLevel,
    NSVariableStatusItemLength,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
    NSWorkspace,
)
from Foundation import NSObject, NSTimer  # noqa: E402
from Quartz import (  # noqa: E402
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGEventFlagMaskCommand,
    kCGHIDEventTap,
)

MODMASK = {"ctrl": 0x40000, "opt": 0x80000, "cmd": 0x100000, "shift": 0x20000, "fn": 0x800000}
REL = sum(MODMASK.values())
KEYS = {
    "ctrl_opt": {"name": "Ctrl + Option", "mods": ("ctrl", "opt")},
    "cmd_opt": {"name": "Cmd + Option", "mods": ("cmd", "opt")},
    "ctrl_shift": {"name": "Ctrl + Shift", "mods": ("ctrl", "shift")},
    "opt_shift": {"name": "Option + Shift", "mods": ("opt", "shift")},
    "ctrl_cmd": {"name": "Ctrl + Cmd", "mods": ("ctrl", "cmd")},
    "ropt": {"name": "Option derecha (sola)", "code": 61, "flag": MODMASK["opt"]},
    "fn": {"name": "fn / 🌐 (ponla en «No hacer nada» en Ajustes > Teclado)", "code": 63, "flag": MODMASK["fn"]},
}
LANGS = {"es": "Español", "en": "English", "auto": "Automático"}

FILLERS = re.compile(r"\b(?:e+h+m*|e+m+|h?m{2,}|u+h+m*|u+m+)\b[,.]?\s*", re.I)
COMMANDS = [
    (re.compile(r"[.,]?\s*\b(?:punto y aparte|nuevo párrafo|new paragraph)\b[.,]?\s*", re.I), ".\n\n"),
    (re.compile(r"[.,]?\s*\b(?:nueva línea|new line)\b[.,]?\s*", re.I), "\n"),
]
HALLUCINATIONS = {
    "gracias por ver el video", "gracias por ver el vídeo", "gracias", "thanks for watching",
    "thank you", "subtítulos realizados por la comunidad de amara.org", "you",
}


def load_cfg() -> dict:
    cfg = {"lang": "es", "key": "ctrl_opt"}
    try:
        cfg.update(json.loads(CFG_FILE.read_text()))
    except Exception:
        pass
    return cfg


def save_cfg(cfg: dict) -> None:
    CFG_DIR.mkdir(exist_ok=True)
    CFG_FILE.write_text(json.dumps(cfg))


def dictionary_prompt() -> str | None:
    if not DICT_FILE.exists():
        DICT_FILE.write_text("# Una palabra o nombre por línea (marcas, nombres propios, jerga)\n")
    words = [w.strip() for w in DICT_FILE.read_text().splitlines() if w.strip() and not w.startswith("#")]
    return ("Vocabulario: " + ", ".join(words) + ".") if words else None


def clean(text: str) -> str:
    text = text.strip()
    for pat, repl in COMMANDS:
        text = pat.sub(repl, text)
    text = FILLERS.sub("", text)
    text = re.sub(r"\.\.+", ".", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    if re.sub(r"[^\w\s]", "", text).lower().strip() in {re.sub(r"[^\w\s]", "", h) for h in HALLUCINATIONS}:
        return ""
    return text


def trim(a: np.ndarray) -> np.ndarray | None:
    """Recorta silencios de los extremos; None si no hay voz."""
    f = 320
    n = len(a) // f
    if n == 0:
        return None
    e = np.sqrt((a[: n * f].reshape(n, f) ** 2).mean(1))
    idx = np.where(e > max(0.004, e.max() * 0.08))[0]
    if len(idx) == 0:
        return None
    return a[max(0, idx[0] - 10) * f : min(n, idx[-1] + 11) * f]


def sound(name: str) -> None:
    subprocess.Popen(["afplay", f"/System/Library/Sounds/{name}.aiff"])


def ax_trusted() -> bool:
    import ctypes

    fn = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
    ).AXIsProcessTrusted
    fn.restype = ctypes.c_bool
    return fn()


def paste(text: str) -> None:
    env = {**os.environ, "LANG": "en_US.UTF-8"}
    if not ax_trusted():  # sin Accesibilidad no se puede pulsar Cmd+V: se deja en el portapapeles
        subprocess.run(["pbcopy"], input=text.encode(), env=env)
        sound("Glass")
        return
    prev = subprocess.run(["pbpaste"], capture_output=True, env=env).stdout
    subprocess.run(["pbcopy"], input=text.encode(), env=env)
    time.sleep(0.05)
    for down in (True, False):
        ev = CGEventCreateKeyboardEvent(None, 9, down)  # 9 = tecla V
        CGEventSetFlags(ev, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, ev)
    time.sleep(0.3)
    subprocess.run(["pbcopy"], input=prev, env=env)


class Dictado:
    def __init__(self) -> None:
        self.cfg = load_cfg()
        self.state = "loading"  # loading | idle | recording | processing
        self.latched = False
        self.down = False
        self.t0 = 0.0
        self.chunks: list[np.ndarray] = []
        self.levels: deque[float] = deque([0.0] * 13, maxlen=13)
        self.stream: sd.InputStream | None = None
        self.last_text = ""
        self.cw, self.ch = 44.0, 8.0

    # --- audio ---
    def _on_audio(self, indata, frames, t, status) -> None:
        self.chunks.append(indata.copy())
        rms = float(np.sqrt(np.mean(indata**2)))
        self.levels.append(min(1.0, rms * 18) ** 0.7)

    def start(self) -> None:
        self.chunks.clear()
        self.latched = False
        self.t0 = time.time()
        self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=self._on_audio)
        self.stream.start()
        self.state = "recording"
        sound("Tink")

    def stop(self) -> None:
        self.stream.stop()
        self.stream.close()
        sound("Pop")
        audio = np.concatenate(self.chunks).flatten() if self.chunks else None
        if audio is None or len(audio) < SAMPLE_RATE * 0.3:
            self.state = "idle"
            return
        self.state = "processing"
        threading.Thread(target=self._transcribe, args=(audio,), daemon=True).start()

    # --- transcripción ---
    def _warmup(self) -> None:
        import mlx_whisper

        mlx_whisper.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), path_or_hf_repo=MODEL)
        self.state = "idle"

    def _transcribe(self, audio: np.ndarray) -> None:
        try:
            import mlx_whisper

            audio = trim(audio)
            if audio is None:
                return
            lang = self.cfg["lang"]
            result = mlx_whisper.transcribe(
                audio,
                path_or_hf_repo=MODEL,
                language=None if lang == "auto" else lang,
                initial_prompt=dictionary_prompt(),
                condition_on_previous_text=False,
            )
            text = clean(result["text"])
            if text:
                self.last_text = text
                CFG_DIR.mkdir(exist_ok=True)
                with LOG_FILE.open("a") as f:
                    f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {text}\n")
                paste(text)
        except Exception as exc:
            print("Error transcribiendo:", exc, flush=True)
            sound("Basso")
        finally:
            self.state = "idle"

    # --- tecla ---
    def set_down(self, down: bool) -> None:
        if down != self.down:
            self.down = down
            self.key_event(down)

    def key_event(self, down: bool) -> None:
        if self.state == "loading":
            if down:
                sound("Basso")
            return
        if down:
            if self.state == "recording" and self.latched:
                self.stop()
            elif self.state == "idle":
                self.start()
        elif self.state == "recording" and not self.latched:
            if time.time() - self.t0 < TAP_MAX:
                self.latched = True
            else:
                self.stop()


D = Dictado()


class Pill(NSView):
    def drawRect_(self, _rect):
        st = D.state
        bw = self.bounds().size.width
        tw, th = {"recording": (124, 34), "processing": (84, 30), "loading": (84, 30)}.get(st, (44, 8))
        D.cw += (tw - D.cw) * 0.25
        D.ch += (th - D.ch) * 0.25
        x, y = (bw - D.cw) / 2, 4
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(x, y, D.cw, D.ch), D.ch / 2, D.ch / 2
        )
        NSColor.colorWithCalibratedWhite_alpha_(0.06, 0.93).setFill()
        path.fill()
        NSColor.colorWithCalibratedWhite_alpha_(1, 0.28).setStroke()
        path.setLineWidth_(1)
        path.stroke()
        cy = y + D.ch / 2
        if st == "recording" and D.ch > 20:
            NSColor.whiteColor().setFill()
            for i, lvl in enumerate(D.levels):
                h = 4 + lvl * (D.ch - 14)
                bx = bw / 2 - 39 + i * 6
                NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    NSMakeRect(bx, cy - h / 2, 3, h), 1.5, 1.5
                ).fill()
            if D.latched:
                NSColor.systemRedColor().setFill()
                NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(x + 12, cy - 3.5, 7, 7)).fill()
        elif st in ("processing", "loading") and D.ch > 20:
            t = time.time()
            for i in range(3):
                a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 6 - i * 0.9))
                NSColor.colorWithCalibratedWhite_alpha_(1, a).setFill()
                NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(bw / 2 - 5 + (i - 1) * 14 - 3, cy - 3, 6, 6)).fill()


class Delegate(NSObject):
    def tick_(self, _timer):
        self.pill.setNeedsDisplay_(True)
        scr = NSScreen.mainScreen().visibleFrame()
        self.panel.setFrameOrigin_((scr.origin.x + scr.size.width / 2 - 110, scr.origin.y + 6))
        sym = {"recording": "mic.fill", "processing": "ellipsis", "loading": "ellipsis"}.get(D.state, "waveform")
        if sym != self.sym:
            self.sym = sym
            img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(sym, "Dictado")
            if img:
                img.setTemplate_(True)
                self.item.button().setImage_(img)

    def setLang_(self, sender):
        D.cfg["lang"] = sender.representedObject()
        save_cfg(D.cfg)
        self.refresh_checks()

    def setKey_(self, sender):
        D.cfg["key"] = sender.representedObject()
        save_cfg(D.cfg)
        self.refresh_checks()

    def pasteLast_(self, _sender):
        if D.last_text:
            threading.Thread(target=paste, args=(D.last_text,), daemon=True).start()

    def openHistory_(self, _sender):
        LOG_FILE.touch()
        NSWorkspace.sharedWorkspace().openFile_(str(LOG_FILE))

    def openDict_(self, _sender):
        dictionary_prompt()
        NSWorkspace.sharedWorkspace().openFile_(str(DICT_FILE))

    def quit_(self, _sender):
        NSApplication.sharedApplication().terminate_(None)

    def refresh_checks(self):
        for it in self.lang_items:
            it.setState_(1 if it.representedObject() == D.cfg["lang"] else 0)
        for it in self.key_items:
            it.setState_(1 if it.representedObject() == D.cfg["key"] else 0)


def add_item(menu, title, action=None, target=None, obj=None):
    it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
    if target:
        it.setTarget_(target)
    if obj is not None:
        it.setRepresentedObject_(obj)
    menu.addItem_(it)
    return it


def on_flags(event) -> None:
    spec = KEYS.get(D.cfg["key"]) or KEYS["ctrl_opt"]
    flags = int(event.modifierFlags())
    if os.environ.get("DICTADO_DEBUG"):
        print(f"flags={hex(flags)} keycode={event.keyCode()} estado={D.state}", flush=True)
    if "code" in spec:
        if event.keyCode() == spec["code"]:
            D.set_down(bool(flags & spec["flag"]))
    else:
        D.set_down((flags & REL) == sum(MODMASK[m] for m in spec["mods"]))


def main() -> None:
    CFG_DIR.mkdir(exist_ok=True)
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    delegate = Delegate.alloc().init()
    app.setDelegate_(delegate)

    # widget flotante (no roba el foco ni bloquea clics)
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, 220, 46),
        NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
        NSBackingStoreBuffered,
        False,
    )
    panel.setOpaque_(False)
    panel.setBackgroundColor_(NSColor.clearColor())
    panel.setHasShadow_(False)
    panel.setIgnoresMouseEvents_(True)
    panel.setLevel_(NSStatusWindowLevel)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehaviorStationary
        | NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    pill = Pill.alloc().initWithFrame_(NSMakeRect(0, 0, 220, 46))
    panel.setContentView_(pill)
    panel.orderFrontRegardless()

    # icono de la barra de menú
    item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
    item.button().setTitle_("🎙")
    menu = NSMenu.alloc().init()
    add_item(menu, "Mantén la tecla y habla · pulsación corta = bloquear").setEnabled_(False)
    menu.addItem_(NSMenuItem.separatorItem())
    lang_menu, key_menu = NSMenu.alloc().init(), NSMenu.alloc().init()
    delegate.lang_items = [add_item(lang_menu, n, "setLang:", delegate, k) for k, n in LANGS.items()]
    delegate.key_items = [add_item(key_menu, v["name"], "setKey:", delegate, k) for k, v in KEYS.items()]
    add_item(menu, "Idioma").setSubmenu_(lang_menu)
    add_item(menu, "Tecla de dictado").setSubmenu_(key_menu)
    menu.addItem_(NSMenuItem.separatorItem())
    add_item(menu, "Pegar último texto", "pasteLast:", delegate)
    add_item(menu, "Abrir historial", "openHistory:", delegate)
    add_item(menu, "Editar diccionario", "openDict:", delegate)
    menu.addItem_(NSMenuItem.separatorItem())
    add_item(menu, "Salir", "quit:", delegate)
    item.setMenu_(menu)

    delegate.panel, delegate.pill, delegate.item, delegate.sym = panel, pill, item, None
    delegate.refresh_checks()

    try:  # pide permisos de monitorización y de pegado la primera vez
        from Quartz import CGRequestListenEventAccess, CGRequestPostEventAccess

        CGRequestListenEventAccess()
        CGRequestPostEventAccess()
    except Exception:
        pass
    try:
        import ctypes

        from Quartz import CGPreflightListenEventAccess

        AXIsProcessTrusted = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        ).AXIsProcessTrusted
        AXIsProcessTrusted.restype = ctypes.c_bool

        print(f"Permisos -> Monitorización de entrada: {CGPreflightListenEventAccess()} | Accesibilidad: {AXIsProcessTrusted()}", flush=True)
    except Exception as exc:
        print("No se pudo comprobar permisos:", exc, flush=True)
    monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSEventMaskFlagsChanged, on_flags)  # noqa: F841

    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(1 / 30, delegate, "tick:", None, True)
    threading.Thread(target=D._warmup, daemon=True).start()
    print("Cargando modelo (la primera vez descarga ~1.6 GB)... el widget muestra puntos hasta que esté listo.", flush=True)
    app.run()


if __name__ == "__main__":
    main()
