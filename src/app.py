import datetime
import base64
import binascii
import logging
import os
import secrets
import time
import urllib.parse
from pathlib import Path

from flask import Flask, render_template_string, request, jsonify, send_file
from werkzeug.utils import secure_filename
import requests

app = Flask(__name__)
API_TOKEN = os.environ.get('ASISTENTE_API_TOKEN') or secrets.token_urlsafe(32)

# Configuración de LM Studio
# Se soportan varios nombres de host para cubrir Docker Desktop, Docker Compose,
# Dev Containers y ejecuciones locales sin cambios de configuración.
def normalize_lm_studio_url(value):
    candidate = (value or "").strip()
    if not candidate:
        return "http://127.0.0.1:1234/v1/chat/completions"

    candidate = candidate.rstrip('/')
    if candidate.endswith('/chat/completions'):
        return candidate
    if candidate.endswith('/v1'):
        return f"{candidate}/chat/completions"
    return f"{candidate}/v1/chat/completions"


LM_STUDIO_URL = normalize_lm_studio_url(os.environ.get("LM_STUDIO_URL"))
TEXT_EXTENSIONS = {'txt', 'md', 'csv', 'json', 'py', 'js', 'html', 'css', 'xml'}
AUDIO_MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT_ATTACHMENT_BYTES = 1_000_000
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_REQUEST_BYTES = 5 * 1024 * 1024
MAX_HISTORY_MESSAGES = 40
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONVERSATIONS_FOLDER = PROJECT_ROOT / 'conversaciones_guardadas'

app.config.update(
    MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES,
    MAX_FORM_MEMORY_SIZE=MAX_REQUEST_BYTES,
    MAX_FORM_PARTS=16,
)

# No se registran peticiones: las rutas pueden transportar texto e imágenes privados.
logging.getLogger('werkzeug').disabled = True
app.logger.disabled = True

chat_history = []
model_settings = {'vision_enabled': True, 'thinking_enabled': False, 'temperature': 1.0}

HTML_PAGE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Asistente Multimodal Avanzado - LM Studio</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='icons.css') }}">
    <style>
        :root {
            --bg-main: #131314;
            --bg-sidebar: #1e1f20;
            --bg-chat: #131314;
            --bg-msg-user: #282a2d;
            --bg-msg-ai: transparent;
            --text-main: #e3e3e3;
            --text-muted: #aaaaaa;
            --accent: #74c0fc;
            --accent-hover: #51a2e0;
            --border-color: #444746;
            --bg-control: #202124;
            --bg-control-hover: #2b2c2f;
            --bg-status: #232428;
            --bg-new-chat: #2b2c2f;
            --line-color: #282828;
        }
        body.light-theme {
            --bg-main: #f4f6f8;
            --bg-sidebar: #ffffff;
            --bg-chat: #f4f6f8;
            --bg-msg-user: #dceeff;
            --bg-msg-ai: transparent;
            --text-main: #1f2933;
            --text-muted: #52606d;
            --accent: #1769aa;
            --accent-hover: #0f5a91;
            --border-color: #c9d2dc;
            --bg-control: #ffffff;
            --bg-control-hover: #e8eef4;
            --bg-status: #edf2f7;
            --bg-new-chat: #eef2f6;
            --line-color: #d9e2ec;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: var(--bg-main); color: var(--text-main); display: flex; height: 100vh; overflow: hidden; }

        /* Sidebar */
        .sidebar { width: 280px; background: var(--bg-sidebar); display: flex; flex-direction: column; padding: 18px 16px; border-right: 1px solid var(--border-color); justify-content: space-between; transition: width 0.2s, padding 0.2s; }
        body.sidebar-hidden .sidebar { width: 0; padding-left: 0; padding-right: 0; overflow: hidden; border-right: 0; }
        body.sidebar-hidden .sidebar > * { opacity: 0; pointer-events: none; }
        .new-chat-btn { background: var(--bg-new-chat); border: 1px solid var(--border-color); color: var(--text-main); padding: 12px 14px; border-radius: 24px; cursor: pointer; display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 15px; transition: background 0.2s, transform 0.15s; }
        .new-chat-btn:hover { background: var(--bg-control-hover); transform: translateY(-1px); }

        .status-container { display: flex; align-items: center; gap: 10px; padding: 12px 14px; background: var(--bg-status); border-radius: 12px; font-size: 13px; margin: 15px 0; }
        .led { width: 12px; height: 12px; border-radius: 50%; background: #00e676; box-shadow: 0 0 8px #00e676; }
        .led.listening { background: #ff1744; box-shadow: 0 0 8px #ff1744; animation: pulse 1.2s infinite; }
        .led.thinking { background: #ffea00; box-shadow: 0 0 8px #ffea00; animation: pulse 1.2s infinite; }

        @keyframes pulse { 0% { opacity: 0.4; } 50% { opacity: 1; } 100% { opacity: 0.4; } }

        .controls-group { display: flex; flex-direction: column; gap: 15px; margin-top: 20px; }
        .control-item { display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: var(--text-muted); }
        .control-item input[type="range"] { accent-color: var(--accent); height: 28px; }
        .temperature-control { display: flex; align-items: center; gap: 10px; }
        .temperature-control input[type="range"] { flex: 1; min-width: 0; }
        .temperature-value { width: 72px; background: var(--bg-control-hover); color: var(--text-main); border: 1px solid var(--border-color); border-radius: 8px; padding: 7px 8px; font: inherit; text-align: right; }
        .toggle-container { display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; }
        .toggle-container input[type="checkbox"] { width: 15px; height: 15px; accent-color: var(--accent); }

        .sidebar-footer { font-size: 11px; color: var(--text-muted); text-align: center; border-top: 1px solid #333; padding-top: 12px; }
        .sidebar-footer-actions { display: flex; gap: 8px; margin-bottom: 10px; }
        .sidebar-footer-actions .btn-mini { flex: 1; justify-content: center; }
        .settings-panel { position: fixed; left: 276px; bottom: 20px; z-index: 30; width: min(340px, calc(100vw - 32px)); background: var(--bg-control); border: 1px solid var(--border-color); border-radius: 12px; padding: 18px; box-shadow: 0 12px 36px rgba(0,0,0,.45); }
        .settings-panel[hidden] { display: none; }
        .settings-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
        .settings-header h2 { font-size: 15px; font-weight: 600; }
        .settings-close { width: 28px; height: 28px; }
        .settings-panel select { width: 100%; background: var(--bg-control-hover); color: var(--text-main); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 12px; font-size: 14px; }
        .settings-panel input[type="text"] { width: 100%; background: var(--bg-control-hover); color: var(--text-main); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 12px; font: inherit; }
        .settings-panel .control-item { margin-bottom: 14px; }
        .settings-panel .control-item:last-child { margin-bottom: 0; }
        .range-with-value { display: flex; align-items: center; gap: 10px; }
        .range-with-value input { flex: 1; }
        .range-value { min-width: 36px; text-align: right; color: var(--text-main); }
        .response-meta { display: flex; flex-wrap: wrap; gap: 6px 12px; color: var(--text-muted); font-size: 11px; padding: 0 4px 2px; }
        .response-meta span { display: inline-flex; align-items: center; gap: 5px; }
        .response-meta i { color: var(--accent); }

        /* Main Chat Area */
        .main-content { flex: 1; display: flex; flex-direction: column; background: var(--bg-chat); height: 100vh; position: relative; }
        .chat-header { height: 62px; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; border-bottom: 1px solid var(--line-color); }
        .chat-header h1 { font-size: 18px; font-weight: 600; }
        .export-btns { display: flex; gap: 8px; }
        .btn-mini { background: transparent; border: 1px solid var(--border-color); color: var(--text-main); padding: 7px 12px; border-radius: 8px; font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 6px; }
        .btn-mini:hover { background: #232428; }
        .header-actions { display: flex; align-items: center; gap: 10px; }
        .tooltip-btn { position: relative; }
        .tooltip-btn:hover::after { content: attr(data-tooltip); position: absolute; top: calc(100% + 8px); right: 0; z-index: 10; white-space: nowrap; background: #000; color: #fff; padding: 5px 8px; border-radius: 4px; font-size: 11px; }
        .message-actions { display: flex; gap: 4px; opacity: 1; transition: opacity 0.15s; }
        .message-actions .icon-btn { width: 28px; height: 28px; font-size: 14px; color: var(--text-muted); border: 1px solid transparent; }
        .message-actions .icon-btn:hover { color: var(--text-main); border-color: var(--border-color); }

        .chat-history { flex: 1; overflow-y: auto; padding: 24px 0; display: flex; flex-direction: column; }
        .chat-row { width: 100%; display: flex; padding: 16px 24px; gap: 16px; }
        .chat-row.user-row { justify-content: flex-end; }

        .avatar { width: 32px; height: 32px; border-radius: 50%; background: #37393e; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; }
        .chat-row.user-row .avatar { order: 2; background: var(--accent); color: #000; }

        .message-content { max-width: 65%; display: flex; flex-direction: column; gap: 8px; }
        .chat-row.user-row .message-content { align-items: flex-end; }

        .bubble { padding: 14px 16px; border-radius: 14px; font-size: 15px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
        .chat-row.user-row .bubble { background: var(--bg-msg-user); color: var(--text-main); border-bottom-right-radius: 2px; }
        .chat-row.ai-row .bubble { background: var(--bg-msg-ai); color: var(--text-main); }

        .attached-img { max-width: 250px; max-height: 250px; border-radius: 8px; border: 1px solid var(--border-color); margin-bottom: 4px; object-fit: cover; }

        /* Input Area */
        .input-area-container { padding: 0 24px 24px 24px; display: flex; flex-direction: column; align-items: center; }
        .input-box-wrapper { width: 100%; max-width: 760px; background: var(--bg-control); border: 1px solid var(--border-color); border-radius: 28px; padding: 8px 16px; display: flex; flex-direction: column; position: relative; }
        .input-box-wrapper.dragover { border-color: var(--accent); background: #28292d; }

        .preview-pane { display: flex; flex-wrap: wrap; gap: 10px; padding: 4px 0 8px 0; border-bottom: 1px solid #3c4043; margin-bottom: 8px; }
        .preview-item { position: relative; width: 60px; height: 60px; border-radius: 6px; overflow: hidden; border: 1px solid var(--border-color); }
        .preview-item img { width: 100%; height: 100%; object-fit: cover; }
        .preview-file { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 22px; color: var(--accent); }
        .preview-item .remove-btn { position: absolute; top: 2px; right: 2px; background: rgba(0,0,0,0.7); color: white; border: none; border-radius: 50%; width: 16px; height: 16px; font-size: 10px; cursor: pointer; display: flex; align-items: center; justify-content: center; }

        .mode-controls { display: flex; gap: 6px; padding: 2px 0 8px 0; }
        .mode-btn { background: transparent; border: 1px solid transparent; color: var(--text-muted); padding: 5px 9px; border-radius: 6px; cursor: pointer; font-size: 12px; display: inline-flex; align-items: center; gap: 6px; }
        .mode-btn:hover { background: var(--bg-control-hover); color: var(--text-main); }
        .mode-btn.active { background: rgba(116,192,252,0.12); border-color: var(--accent); color: var(--accent); }

        .input-row { display: flex; align-items: flex-end; width: 100%; gap: 10px; }
        .icon-btn { background: transparent; border: none; color: var(--text-main); width: 42px; height: 42px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 19px; transition: background 0.2s, transform 0.15s; flex-shrink: 0; }
        .icon-btn:hover { background: var(--bg-control-hover); transform: translateY(-1px); }
        .icon-btn.active-mic { color: #ff1744; background: rgba(255,23,68,0.1); }

        textarea { flex: 1; background: transparent; border: none; outline: none; color: var(--text-main); font-family: inherit; font-size: 16px; resize: none; max-height: 180px; min-height: 28px; padding: 10px 0; line-height: 1.5; }

        #send-btn { color: var(--accent); }
        #send-btn:disabled { color: #5f6368; cursor: not-allowed; }

        /* Ocultar inputs nativos */
        #file-input { display: none; }
        @media (max-width: 700px) { .sidebar { position: absolute; z-index: 20; height: 100%; } .settings-panel { left: 16px; bottom: 16px; } .chat-header { padding: 0 12px; } .chat-row { padding-left: 12px; padding-right: 12px; } .message-content { max-width: 85%; } }
    </style>
</head>
<body>

    <!-- Barra Lateral -->
    <div class="sidebar">
        <div>
            <button class="new-chat-btn" id="clear-btn">
                <i class="fa-solid fa-plus"></i> <span data-i18n="newChat">Nuevo chat</span>
            </button>

            <div class="status-container">
                <div class="led" id="status-led"></div>
                <span id="status-text">Listo (Visión Real)</span>
            </div>

            <div class="controls-group">
                <div class="control-item">
                    <label class="toggle-container"><input type="checkbox" id="sidebar-vision-toggle" checked> <span data-i18n="vision">Visión</span> <span id="vision-sync-state">Sincronizada</span></label>
                </div>
                <div class="control-item">
                    <label class="toggle-container"><input type="checkbox" id="sidebar-thinking-toggle"> <span data-i18n="think">Think</span> <span id="thinking-sync-state">Desactivado</span></label>
                </div>
                <div class="control-item">
                    <label for="temp-slider"><span data-i18n="creativity">Creatividad (Temp)</span></label>
                    <div class="temperature-control">
                        <input type="range" id="temp-slider" min="0" max="1.5" step="0.1" value="1.0">
                        <input type="number" id="temp-input" class="temperature-value" min="0" max="1.5" step="0.1" value="1.0" aria-label="Temperatura">
                    </div>
                </div>
                <div class="control-item" style="margin-top: 10px;">
                    <label class="toggle-container">
                        <input type="checkbox" id="tts-toggle" checked> <span data-i18n="autoVoice">Auto-voz (lectura)</span>
                    </label>
                </div>
            </div>
        </div>

        <div class="sidebar-footer">
            <div class="sidebar-footer-actions">
                <button class="btn-mini" id="settings-btn" title="Abrir configuración" aria-label="Abrir configuración"><i class="fa-solid fa-gear"></i><span data-i18n="settings">Ajustes</span></button>
                <button class="btn-mini" id="stop-tts-btn" title="Detener lectura" disabled><i class="fa-solid fa-volume-xmark"></i> <span data-i18n="stopAudio">Detener Audio</span></button>
            </div>
            <p>LM Studio Multimodal UI v2.0</p>
        </div>
    </div>

    <section class="settings-panel" id="settings-panel" hidden aria-labelledby="settings-title">
        <div class="settings-header">
            <h2 id="settings-title" data-i18n="settings">Ajustes</h2>
            <button class="icon-btn settings-close" id="settings-close" title="Cerrar" aria-label="Cerrar"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <div class="control-item">
            <label for="interface-language" data-i18n="interfaceLanguage">Idioma de la interfaz</label>
            <select id="interface-language"><option value="es">Español</option><option value="en">English</option></select>
        </div>
        <div class="control-item">
            <label for="interface-theme" data-i18n="interfaceTheme">Tema de la interfaz</label>
            <select id="interface-theme"><option value="dark">Oscuro</option><option value="light">Claro</option></select>
        </div>
        <div class="control-item">
            <label for="voice-select" data-i18n="voice">Voz de respuesta</label>
            <select id="voice-select"><option value="" data-i18n="defaultVoice">Voz predeterminada</option></select>
        </div>
        <div class="control-item">
            <label for="speech-language" data-i18n="speechLanguage">Idioma de lectura</label>
            <select id="speech-language"><option value="es-ES">Español</option><option value="en-US">English</option><option value="fr-FR">Français</option><option value="de-DE">Deutsch</option></select>
        </div>
        <div class="control-item">
            <label for="speech-rate" data-i18n="speechRate">Velocidad de lectura</label>
            <div class="range-with-value"><input type="range" id="speech-rate" min="0.5" max="2" step="0.1" value="1"><span class="range-value" id="speech-rate-value">1.0x</span></div>
        </div>
        <div class="control-item">
            <label for="speech-pitch" data-i18n="speechPitch">Tono de voz</label>
            <div class="range-with-value"><input type="range" id="speech-pitch" min="0.5" max="2" step="0.1" value="1"><span class="range-value" id="speech-pitch-value">1.0</span></div>
        </div>
        <div class="control-item">
            <label for="mic-shortcut" data-i18n="micShortcut">Atajo del micrófono</label>
            <input type="text" id="mic-shortcut" value="Ctrl+Shift+M" readonly aria-describedby="mic-shortcut-help">
            <small id="mic-shortcut-help" data-i18n="micShortcutHelp">Pulsa una combinación de teclas para configurarla</small>
        </div>
        <label class="toggle-container"><input type="checkbox" id="tts-toggle-settings" checked> <span data-i18n="autoRead">Leer respuestas automáticamente</span></label>
    </section>

    <!-- Contenido Principal -->
    <div class="main-content">
        <div class="chat-header">
            <div class="header-actions">
                <button class="icon-btn tooltip-btn" id="sidebar-toggle" data-tooltip="Mostrar u ocultar panel" aria-label="Mostrar u ocultar panel"><i class="fa-solid fa-bars" aria-hidden="true"></i></button>
                <h1 data-i18n="assistant">Asistente Inteligente</h1>
            </div>
            <div class="export-btns">
                <button class="btn-mini tooltip-btn" id="exp-md" data-tooltip="Guardar como Markdown" title="Guardar como Markdown"><i class="fa-solid fa-file-lines" aria-hidden="true"></i> .MD</button>
                <button class="btn-mini tooltip-btn" id="exp-txt" data-tooltip="Guardar como texto" title="Guardar como texto"><i class="fa-solid fa-file-lines" aria-hidden="true"></i> .TXT</button>
            </div>
        </div>

        <div class="chat-history" id="chat-history">
            <div class="chat-row ai-row">
                <div class="avatar"><i class="fa-solid fa-robot"></i></div>
                <div class="message-content">
                    <div class="bubble" data-i18n="welcome">¡Hola! Interfaz unificada con soporte de visión local en tiempo real activa. Puedes soltar imágenes aquí, cargarlas con el clip, escribir, o usar el micrófono en español.</div>
                </div>
            </div>
        </div>

        <div class="input-area-container">
            <div class="input-box-wrapper" id="drop-zone">
                <div class="preview-pane" id="preview-pane" style="display: none;"></div>
                <div class="mode-controls" role="group" aria-label="Modos del modelo">
                    <button class="mode-btn active" id="vision-toggle" type="button" aria-pressed="true" title="Activar o desactivar el envío de imágenes">
                        <i class="fa-solid fa-eye"></i> <span data-i18n="vision">Visión</span>
                    </button>
                    <button class="mode-btn" id="thinking-toggle" type="button" aria-pressed="false" title="Activar o desactivar el razonamiento del modelo">
                        <i class="fa-solid fa-brain"></i> <span data-i18n="think">Think</span>
                    </button>
                </div>
                <div class="input-row">
                    <button class="icon-btn" id="clip-btn" title="Adjuntar imagen o archivo" aria-label="Adjuntar imagen o archivo"><i class="fa-solid fa-paperclip" aria-hidden="true"></i></button>
                    <input type="file" id="file-input" accept="image/*,.txt,.md,.csv,.json,.py,.js,.html,.css,.xml">

                    <textarea id="user-input" placeholder="Pregunta algo o envía una imagen..." rows="1"></textarea>

                    <button class="icon-btn" id="mic-btn" title="Hablar en Español"><i class="fa-solid fa-microphone"></i></button>
                    <button class="icon-btn" id="delete-chat-btn" title="Borrar chat" aria-label="Borrar chat"><i class="fa-solid fa-trash-can" aria-hidden="true"></i></button>
                    <button class="icon-btn" id="send-btn" disabled title="Enviar Mensaje"><i class="fa-solid fa-paper-plane"></i></button>
                </div>
            </div>
        </div>
    </div>

<script>
    const API_TOKEN = {{ api_token|tojson }};
    async function apiFetch(url, options = {}) {
        const headers = new Headers(options.headers || {});
        headers.set('X-Asistente-Token', API_TOKEN);
        return fetch(url, {...options, headers});
    }

    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const micBtn = document.getElementById('mic-btn');
    const clipBtn = document.getElementById('clip-btn');
    const fileInput = document.getElementById('file-input');
    const previewPane = document.getElementById('preview-pane');
    const dropZone = document.getElementById('drop-zone');
    const statusLed = document.getElementById('status-led');
    const statusText = document.getElementById('status-text');
    const tempSlider = document.getElementById('temp-slider');
    const tempInput = document.getElementById('temp-input');
    const ttsToggle = document.getElementById('tts-toggle');
    const stopTtsBtn = document.getElementById('stop-tts-btn');
    const clearBtn = document.getElementById('clear-btn');
    const deleteChatBtn = document.getElementById('delete-chat-btn');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebarVisionToggle = document.getElementById('sidebar-vision-toggle');
    const sidebarThinkingToggle = document.getElementById('sidebar-thinking-toggle');
    const visionSyncState = document.getElementById('vision-sync-state');
    const thinkingSyncState = document.getElementById('thinking-sync-state');
    const visionToggle = document.getElementById('vision-toggle');
    const thinkingToggle = document.getElementById('thinking-toggle');
    const settingsBtn = document.getElementById('settings-btn');
    const settingsPanel = document.getElementById('settings-panel');
    const settingsClose = document.getElementById('settings-close');
    const interfaceLanguage = document.getElementById('interface-language');
    const interfaceTheme = document.getElementById('interface-theme');
    const voiceSelect = document.getElementById('voice-select');
    const speechLanguage = document.getElementById('speech-language');
    const speechRate = document.getElementById('speech-rate');
    const speechRateValue = document.getElementById('speech-rate-value');
    const speechPitch = document.getElementById('speech-pitch');
    const speechPitchValue = document.getElementById('speech-pitch-value');
    const micShortcut = document.getElementById('mic-shortcut');
    const settingsTtsToggle = document.getElementById('tts-toggle-settings');

    let base64Image = null;
    let selectedFileName = null;
    let selectedAttachment = null;
    let visionEnabled = true;
    let thinkingEnabled = false;
    let synth = window.speechSynthesis;
    let currentUtterance = null;
    let availableVoices = [];
    const translations = {
        es: { settings: 'Ajustes', stopAudio: 'Detener audio', interfaceLanguage: 'Idioma de la interfaz', interfaceTheme: 'Tema de la interfaz', voice: 'Voz de respuesta', defaultVoice: 'Voz predeterminada', speechLanguage: 'Idioma de lectura', speechRate: 'Velocidad de lectura', speechPitch: 'Tono de voz', micShortcut: 'Atajo del micrófono', micShortcutHelp: 'Pulsa una combinación de teclas para configurarla', autoRead: 'Leer respuestas automáticamente', assistant: 'Asistente inteligente', welcome: '¡Hola! Interfaz unificada con soporte de visión local en tiempo real activa. Puedes soltar imágenes aquí, cargarlas con el clip, escribir, o usar el micrófono en español.', newChat: 'Nuevo chat', vision: 'Visión', think: 'Think', creativity: 'Creatividad (Temp)', autoVoice: 'Auto-voz (lectura)' },
        en: { settings: 'Settings', stopAudio: 'Stop audio', interfaceLanguage: 'Interface language', interfaceTheme: 'Interface theme', voice: 'Response voice', defaultVoice: 'Default voice', speechLanguage: 'Reading language', speechRate: 'Reading speed', speechPitch: 'Voice pitch', micShortcut: 'Microphone shortcut', micShortcutHelp: 'Press a key combination to configure it', autoRead: 'Read responses automatically', assistant: 'Smart assistant', welcome: 'Hello! The unified interface with real-time local vision is active. You can drop images here, attach them, type, or use the microphone in English.', newChat: 'New chat', vision: 'Vision', think: 'Think', creativity: 'Creativity (Temp)', autoVoice: 'Auto voice (reading)' }
    };

    function applyInterfaceLanguage(language) {
        const dictionary = translations[language] || translations.es;
        document.documentElement.lang = language;
        document.querySelectorAll('[data-i18n]').forEach((element) => {
            const translation = dictionary[element.dataset.i18n];
            if (translation) element.textContent = translation;
        });
        localStorage.setItem('interfaceLanguage', language);
    }

    function applyTheme(theme) {
        document.body.classList.toggle('light-theme', theme === 'light');
        interfaceTheme.value = theme;
        localStorage.setItem('interfaceTheme', theme);
    }

    function populateVoices() {
        if (!synth) return;
        availableVoices = synth.getVoices().sort((first, second) => first.name.localeCompare(second.name));
        const selectedVoice = voiceSelect.value;
        voiceSelect.innerHTML = `<option value="">${translations[interfaceLanguage.value].defaultVoice}</option>`;
        availableVoices.forEach((voice, index) => {
            const option = document.createElement('option');
            option.value = String(index);
            option.textContent = `${voice.name} (${voice.lang})`;
            voiceSelect.appendChild(option);
        });
        voiceSelect.value = selectedVoice || localStorage.getItem('voiceIndex') || '';
    }

    function updateSpeechValueLabels() {
        speechRateValue.textContent = `${Number(speechRate.value).toFixed(1)}x`;
        speechPitchValue.textContent = Number(speechPitch.value).toFixed(1);
    }

    function loadSpeechSettings() {
        interfaceLanguage.value = localStorage.getItem('interfaceLanguage') || 'es';
        applyTheme(localStorage.getItem('interfaceTheme') || 'dark');
        speechLanguage.value = localStorage.getItem('speechLanguage') || 'es-ES';
        speechRate.value = localStorage.getItem('speechRate') || '1';
        speechPitch.value = localStorage.getItem('speechPitch') || '1';
        micShortcut.value = localStorage.getItem('micShortcut') || 'Ctrl+Shift+M';
        ttsToggle.checked = localStorage.getItem('autoRead') !== 'false';
        settingsTtsToggle.checked = ttsToggle.checked;
        applyInterfaceLanguage(interfaceLanguage.value);
        updateSpeechValueLabels();
        populateVoices();
    }

    settingsBtn.addEventListener('click', () => { settingsPanel.hidden = !settingsPanel.hidden; populateVoices(); });
    settingsClose.addEventListener('click', () => { settingsPanel.hidden = true; });
    interfaceLanguage.addEventListener('change', () => { applyInterfaceLanguage(interfaceLanguage.value); populateVoices(); });
    interfaceTheme.addEventListener('change', () => applyTheme(interfaceTheme.value));
    voiceSelect.addEventListener('change', () => localStorage.setItem('voiceIndex', voiceSelect.value));
    speechLanguage.addEventListener('change', () => localStorage.setItem('speechLanguage', speechLanguage.value));
    speechRate.addEventListener('input', () => { updateSpeechValueLabels(); localStorage.setItem('speechRate', speechRate.value); });
    speechPitch.addEventListener('input', () => { updateSpeechValueLabels(); localStorage.setItem('speechPitch', speechPitch.value); });
    micShortcut.addEventListener('keydown', (event) => {
        event.preventDefault();
        if (['Control', 'Shift', 'Alt', 'Meta'].includes(event.key)) return;
        const keys = [];
        if (event.ctrlKey) keys.push('Ctrl');
        if (event.altKey) keys.push('Alt');
        if (event.shiftKey) keys.push('Shift');
        if (event.metaKey) keys.push('Meta');
        const key = event.key.length === 1 ? event.key.toUpperCase() : event.key;
        if (!keys.length || ['Control', 'Shift', 'Alt', 'Meta'].includes(key)) return;
        keys.push(key);
        micShortcut.value = keys.join('+');
        localStorage.setItem('micShortcut', micShortcut.value);
    });
    settingsTtsToggle.addEventListener('change', () => { ttsToggle.checked = settingsTtsToggle.checked; localStorage.setItem('autoRead', String(ttsToggle.checked)); });
    ttsToggle.addEventListener('change', () => { settingsTtsToggle.checked = ttsToggle.checked; localStorage.setItem('autoRead', String(ttsToggle.checked)); });
    if (synth) synth.addEventListener('voiceschanged', populateVoices);
    loadSpeechSettings();

    // Actualizar y sincronizar la temperatura usada por LM Studio.
    let temperatureSyncTimer = null;
    tempSlider.addEventListener('input', () => {
        tempInput.value = Number(tempSlider.value).toFixed(1);
        clearTimeout(temperatureSyncTimer);
        temperatureSyncTimer = setTimeout(() => syncTemperature(Number(tempSlider.value)), 180);
    });
    tempInput.addEventListener('change', () => syncTemperature(Number(tempInput.value)));

    function updateTemperatureControls(value) {
        const normalizedValue = Number(value).toFixed(1);
        tempSlider.value = normalizedValue;
        tempInput.value = normalizedValue;
    }

    async function syncTemperature(temperature) {
        if (!Number.isFinite(temperature) || temperature < 0 || temperature > 1.5) {
            updateTemperatureControls(tempSlider.value);
            statusText.textContent = 'La temperatura debe estar entre 0 y 1.5';
            return;
        }
        try {
            const response = await apiFetch('/api/model-settings', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({temperature})
            });
            if (!response.ok) throw new Error('No se pudo sincronizar la temperatura');
            const settings = await response.json();
            updateTemperatureControls(settings.temperature);
        } catch (error) {
            statusText.textContent = 'Temperatura pendiente de sincronizar';
        }
    }

    async function loadModelSettings() {
        try {
            const response = await apiFetch('/api/model-settings');
            if (!response.ok) throw new Error('No se pudo cargar la configuración');
            const settings = await response.json();
            updateTemperatureControls(settings.temperature);
            updateModelControls(settings);
        } catch (error) {
            statusText.textContent = 'Configuración local';
        }
    }

    loadModelSettings();

    // Habilitar / deshabilitar botón de envío
    userInput.addEventListener('input', () => {
        sendBtn.disabled = (userInput.value.trim() === "" && !base64Image);
        userInput.style.height = 'auto';
        userInput.style.height = userInput.scrollHeight + 'px';
    });

    // Control del Clip de Archivo
    clipBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelect);

    // Soporte Drag and Drop
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if(e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            handleFileSelect({target: fileInput});
        }
    });

    function handleFileSelect(e) {
        const file = e.target.files[0];
        if (!file) return;
        const isImage = file.type.startsWith('image/');
        const maxBytes = isImage ? 10 * 1024 * 1024 : 1000000;
        if ((!isImage && !['txt', 'md', 'csv', 'json', 'py', 'js', 'html', 'css', 'xml'].includes(file.name.split('.').pop().toLowerCase())) || file.size > maxBytes) {
            alert(isImage ? 'La imagen no puede superar 10 MB.' : 'Tipo de archivo no permitido o archivo superior a 1 MB.');
            fileInput.value = '';
            return;
        }
        selectedFileName = file.name;
        selectedAttachment = file;
        const reader = new FileReader();
        reader.onload = function(evt) {
            base64Image = isImage ? evt.target.result.split(',')[1] : null;

            // Mostrar vista previa en la caja
            previewPane.innerHTML = `
                <div class="preview-item">
                    ${base64Image ? `<img src="${evt.target.result}">` : '<div class="preview-file"><i class="fa-solid fa-file-lines" aria-hidden="true"></i></div>'}
                    <button class="remove-btn" onclick="removeSelectedFile()">&times;</button>
                </div>
            `;
            previewPane.style.display = 'flex';
            sendBtn.disabled = false;
        };
        reader.readAsDataURL(file);
    }

    window.removeSelectedFile = function() {
        base64Image = null;
        selectedFileName = null;
        selectedAttachment = null;
        fileInput.value = '';
        previewPane.style.display = 'none';
        previewPane.innerHTML = '';
        sendBtn.disabled = (userInput.value.trim() === "");
    };

    // Configurar API de Voz (Navegador)
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;
    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.lang = 'es-ES';
        recognition.interimResults = false;

        function startVoiceRecognition() {
            if (recognition && recognition.state === 'recording') return;
            if (synth.speaking) synth.cancel();
            try {
                recognition.start();
                setAppState('listening', 'Escuchando voz...');
                micBtn.classList.add('active-mic');
            } catch(e) {
                recognition.stop();
            }
        }

        micBtn.addEventListener('click', startVoiceRecognition);

        function matchesMicShortcut(event) {
            const configured = (micShortcut.value || 'Ctrl+Shift+M').split('+');
            const key = configured.pop();
            return event.key.toUpperCase() === key.toUpperCase()
                && event.ctrlKey === configured.includes('Ctrl')
                && event.shiftKey === configured.includes('Shift')
                && event.altKey === configured.includes('Alt')
                && event.metaKey === configured.includes('Meta');
        }

        document.addEventListener('keydown', (event) => {
            if (!settingsPanel.hidden && document.activeElement === micShortcut) return;
            if (matchesMicShortcut(event)) {
                event.preventDefault();
                startVoiceRecognition();
            }
        });

        recognition.onresult = (event) => {
            const text = event.results[0][0].transcript;
            userInput.value = text;
            userInput.dispatchEvent(new Event('input'));
            sendMessage(); // Auto Enviar al transcribir voz
        };

        recognition.onerror = () => { resetAppState(); };
        recognition.onend = () => { resetAppState(); micBtn.classList.remove('active-mic'); };
    } else {
        micBtn.style.display = 'none';
    }

    function setAppState(state, text) {
        statusLed.className = 'led ' + state;
        statusText.innerText = text;
    }

    function resetAppState() {
        statusLed.className = 'led';
        statusText.innerText = 'Listo (Visión Real)';
    }

    function setMode(toggle, enabled) {
        toggle.classList.toggle('active', enabled);
        toggle.setAttribute('aria-pressed', String(enabled));
    }

    function updateModelControls(settings) {
        visionEnabled = settings.vision_enabled;
        thinkingEnabled = settings.thinking_enabled;
        setMode(visionToggle, visionEnabled);
        setMode(thinkingToggle, thinkingEnabled);
        sidebarVisionToggle.checked = visionEnabled;
        sidebarThinkingToggle.checked = thinkingEnabled;
        visionSyncState.textContent = visionEnabled ? 'Sincronizada' : 'Desactivada';
        thinkingSyncState.textContent = thinkingEnabled ? 'Sincronizado' : 'Desactivado';
    }

    async function syncModelSetting(setting, enabled) {
        try {
            const response = await apiFetch('/api/model-settings', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({[setting]: enabled})
            });
            if (!response.ok) throw new Error('No se pudo sincronizar');
            const settings = await response.json();
            updateModelControls(settings);
            visionSyncState.textContent = visionEnabled ? 'Sincronizada' : 'Desactivada';
            thinkingSyncState.textContent = thinkingEnabled ? 'Sincronizado' : 'Desactivado';
            if (!visionEnabled && base64Image) removeSelectedFile();
        } catch (error) {
            await loadModelSettings();
            alert('No se pudo sincronizar el estado con LM Studio.');
        }
    }

    visionToggle.addEventListener('click', () => {
        visionEnabled = !visionEnabled;
        setMode(visionToggle, visionEnabled);
        syncModelSetting('vision_enabled', visionEnabled);
        if (!visionEnabled && base64Image) removeSelectedFile();
    });

    thinkingToggle.addEventListener('click', () => {
        thinkingEnabled = !thinkingEnabled;
        setMode(thinkingToggle, thinkingEnabled);
        syncModelSetting('thinking_enabled', thinkingEnabled);
    });
    sidebarVisionToggle.addEventListener('change', () => syncModelSetting('vision_enabled', sidebarVisionToggle.checked));
    sidebarThinkingToggle.addEventListener('change', () => syncModelSetting('thinking_enabled', sidebarThinkingToggle.checked));
    sidebarToggle.addEventListener('click', () => document.body.classList.toggle('sidebar-hidden'));

    // Enviar Mensajes a Python
    async function sendMessage() {
        const text = userInput.value.trim();
        const imgToSend = visionEnabled ? base64Image : null;
        const attachmentFile = selectedAttachment;
        const attachmentName = attachmentFile && !imgToSend && !attachmentFile.type.startsWith('image/') ? selectedFileName : null;
        const attachmentText = attachmentFile && !imgToSend ? await readTextAttachment(attachmentFile) : '';
        if (!text && !imgToSend && !attachmentName) return;

        // Renderizar en UI del usuario
        appendRow('user', text, imgToSend);

        // Guardar parámetros actuales y resetear caja
        const promptToSend = text;
        removeSelectedFile();
        userInput.value = '';
        userInput.style.height = 'auto';
        sendBtn.disabled = true;

        setAppState('thinking', 'Procesando en LM Studio...');

        const requestStartedAt = performance.now();
        try {
            const response = await apiFetch('/ask_ai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: promptToSend,
                    image_base64: imgToSend,
                    vision_enabled: visionEnabled,
                    thinking_enabled: thinkingEnabled,
                    attachment_name: attachmentName,
                    attachment_text: attachmentText
                })
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || errorData.response || 'El servidor rechazó la petición');
            }
            const data = await response.json();

            const clientLatencyMs = Math.round(performance.now() - requestStartedAt);
            appendRow('ai', data.response, null, {...(data.metrics || {}), client_latency_ms: clientLatencyMs});
            if (ttsToggle.checked) speakText(data.response);

        } catch (error) {
            appendRow('ai', 'Error al comunicar con el servidor local de Flask o LM Studio. Verifica las conexiones.');
        }

        resetAppState();
    }

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    function appendRow(sender, text, imgBase64 = null, metrics = null) {
        const row = document.createElement('div');
        row.classList.add('chat-row', sender === 'user' ? 'user-row' : 'ai-row');

        let imgHtml = '';
        if (imgBase64) {
            imgHtml = `<img src="data:image/jpeg;base64,${imgBase64}" class="attached-img">`;
        }

        const avatarHtml = sender === 'user' ?
            `<div class="avatar"><i class="fa-solid fa-user"></i></div>` :
            `<div class="avatar"><i class="fa-solid fa-robot"></i></div>`;

        const metricsHtml = sender === 'ai' && metrics ? `<div class="response-meta" aria-label="Métricas de respuesta">
                <span><i class="fa-solid fa-stopwatch"></i> ${metrics.client_latency_ms || metrics.latency_ms || '?'} ms</span>
                <span><i class="fa-solid fa-arrow-up"></i> ${metrics.prompt_tokens ?? '?'} tokens entrada</span>
                <span><i class="fa-solid fa-arrow-down"></i> ${metrics.completion_tokens ?? '?'} tokens salida</span>
                <span><i class="fa-solid fa-microchip"></i> ${escapeHtml(metrics.model || 'LM Studio')}</span>
            </div>` : '';
        const userActionsHtml = sender === 'user' ? `<div class="message-actions">
                    <button class="icon-btn" title="Copiar mensaje" aria-label="Copiar mensaje"><i class="fa-solid fa-copy" aria-hidden="true"></i></button>
                </div>` : `<div class="message-actions">
                    <button class="icon-btn" title="Copiar respuesta" aria-label="Copiar respuesta"><i class="fa-solid fa-copy" aria-hidden="true"></i></button>
                    <button class="icon-btn" title="Leer respuesta" aria-label="Leer respuesta"><i class="fa-solid fa-volume-high" aria-hidden="true"></i></button>
                    <button class="icon-btn" title="Enviar por Gmail" aria-label="Enviar por Gmail"><i class="fa-solid fa-envelope" aria-hidden="true"></i></button>
                    <button class="icon-btn" title="Guardar respuesta" aria-label="Guardar respuesta"><i class="fa-solid fa-download" aria-hidden="true"></i></button>
                </div>`;
        row.innerHTML = `
            ${avatarHtml}
            <div class="message-content">
                ${imgHtml}
                ${metricsHtml}
                <div class="bubble">${escapeHtml(text || '')}</div>
                ${userActionsHtml}
            </div>
        `;
        chatHistory.appendChild(row);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        if (sender === 'ai') wireMessageActions(row, text || '');
    }

    async function readTextAttachment(file) {
        const extension = file.name.split('.').pop().toLowerCase();
        if (file.size > 1000000 || !['txt', 'md', 'csv', 'json', 'py', 'js', 'html', 'css', 'xml'].includes(extension)) return '';
        return await file.text();
    }

    function wireMessageActions(row, text) {
        const buttons = row.querySelectorAll('.message-actions button');
        if (buttons.length === 1) {
            buttons[0].addEventListener('click', () => navigator.clipboard.writeText(text));
            return;
        }
        buttons[0].addEventListener('click', () => navigator.clipboard.writeText(text));
        buttons[1].addEventListener('click', () => speakText(text));
        buttons[2].addEventListener('click', async () => {
            const response = await apiFetch('/api/procesar-gmail', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({texto: text})});
            const data = await response.json();
            window.open(data.url, '_blank');
        });
        buttons[3].addEventListener('click', async () => {
            const response = await apiFetch('/api/generar-nombre-archivo', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({titulo: text.slice(0, 40)})});
            const data = await response.json();
            const blob = new Blob([text], {type: 'text/markdown;charset=utf-8'});
            const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = data.filename; link.click(); URL.revokeObjectURL(link.href);
        });
    }

    function escapeHtml(text) {
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // Texto a Voz (Lectura)
    function speakText(text) {
        if (!synth) return;
        synth.cancel();
        const cleanText = text.replace(/[*_#`]/g, '');
        currentUtterance = new SpeechSynthesisUtterance(cleanText);
        currentUtterance.lang = speechLanguage.value;
        currentUtterance.rate = Number(speechRate.value);
        currentUtterance.pitch = Number(speechPitch.value);
        const selectedVoice = availableVoices[Number(voiceSelect.value)];
        if (selectedVoice) currentUtterance.voice = selectedVoice;
        currentUtterance.onstart = () => stopTtsBtn.disabled = false;
        currentUtterance.onend = () => stopTtsBtn.disabled = true;
        currentUtterance.onerror = () => stopTtsBtn.disabled = true;
        synth.speak(currentUtterance);
    }

    stopTtsBtn.addEventListener('click', () => { if (synth) { synth.cancel(); stopTtsBtn.disabled = true; } });

    // Acciones de Botones de la barra de control
    clearBtn.addEventListener('click', async () => {
        if (synth) synth.cancel();
        await apiFetch('/clear_chat', { method: 'POST' });
        chatHistory.innerHTML = `
            <div class="chat-row ai-row">
                <div class="avatar"><i class="fa-solid fa-robot"></i></div>
                <div class="message-content">
                    <div class="bubble">Historial vaciado. Entorno listo para nuevos prompts o imágenes de Visión.</div>
                </div>
            </div>
        `;
    });

    async function exportChat(format) {
        try {
            const response = await apiFetch(`/export/${format}`);
            if (!response.ok) throw new Error('No se pudo exportar el chat');
            const blob = await response.blob();
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `conversacion.${format}`;
            link.click();
            URL.revokeObjectURL(link.href);
        } catch (error) {
            statusText.textContent = 'No se pudo exportar la conversación';
        }
    }

    document.getElementById('exp-md').addEventListener('click', () => exportChat('md'));
    document.getElementById('exp-txt').addEventListener('click', () => exportChat('txt'));
    deleteChatBtn.addEventListener('click', () => clearBtn.click());
</script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_PAGE, api_token=API_TOKEN)


@app.before_request
def require_local_api_token():
    if request.endpoint in {'home', 'static'} or request.path == '/favicon.ico':
        return None
    supplied_token = request.headers.get('X-Asistente-Token')
    if not secrets.compare_digest(supplied_token or '', API_TOKEN):
        return jsonify({'error': 'No autorizado.'}), 401
    return None

@app.errorhandler(413)
def request_too_large(error):
    return jsonify({"error": "La petición supera el límite de 16 MB."}), 413

@app.route('/ask_ai', methods=['POST'])
def ask_ai():
    global chat_history, model_settings

    if request.content_length and request.content_length > MAX_REQUEST_BYTES:
        return jsonify({"error": f"La petición supera el límite de {MAX_REQUEST_BYTES / (1024 * 1024)} MB."}), 413

    data = request.get_json(silent=True) or {}
    user_prompt = str(data.get('prompt', '') or '').strip()
    image_base64 = data.get('image_base64')
    vision_enabled = bool(data.get('vision_enabled', model_settings.get('vision_enabled', True)))
    thinking_enabled = bool(data.get('thinking_enabled', model_settings.get('thinking_enabled', False)))
    temperature = float(model_settings.get('temperature', 1.0))
    raw_attachment_name = data.get('attachment_name', '')
    attachment_name = secure_filename(raw_attachment_name) if isinstance(raw_attachment_name, str) and raw_attachment_name.strip() else ''
    attachment_text = data.get('attachment_text', '')

    if image_base64 is not None and not isinstance(image_base64, str):
        return jsonify({"error": "La imagen enviada no tiene un formato válido."}), 400
    if not isinstance(attachment_text, str):
        return jsonify({"error": "El contenido del archivo adjunto no es válido."}), 400
    if attachment_name:
        extension = Path(attachment_name).suffix.lower().lstrip('.')
        if extension not in TEXT_EXTENSIONS:
            return jsonify({"error": "El tipo de archivo adjunto no está permitido."}), 400
        if len(attachment_text.encode('utf-8')) > MAX_TEXT_ATTACHMENT_BYTES:
            return jsonify({"error": "El archivo de texto no puede superar 1 MB."}), 413
    if not vision_enabled:
        image_base64 = None
    if not user_prompt and not image_base64 and not attachment_name and not attachment_text:
        return jsonify({"error": "Debes enviar texto, una imagen o un archivo."}), 400

    content_list = []
    if user_prompt:
        content_list.append({"type": "text", "text": user_prompt})

    if attachment_name and not image_base64:
        attachment_note = f"[Archivo adjunto: {attachment_name}]"
        if attachment_text:
            attachment_note += f"\nContenido del archivo:\n{attachment_text[:MAX_TEXT_ATTACHMENT_BYTES]}"
        content_list.append({"type": "text", "text": attachment_note})

    if image_base64:
        content_list.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_base64}"
            }
        })

    if not content_list:
        return jsonify({"error": "Debes enviar texto, una imagen o un archivo."}), 400

    chat_history.append({
        "role": "user",
        "content": content_list if len(content_list) > 1 or image_base64 else user_prompt
    })
    chat_history = chat_history[-MAX_HISTORY_MESSAGES:]

    payload = {
        "messages": chat_history,
        "temperature": temperature,
        "chat_template_kwargs": {
            "enable_thinking": thinking_enabled
        }
    }

    try:
        started_at = time.perf_counter()
        response = requests.post(LM_STUDIO_URL, json=payload, timeout=90)
        response.raise_for_status()
        response_data = response.json()
        choices = response_data.get('choices') or []
        if not choices:
            raise ValueError('LM Studio no devolvió ninguna elección.')
        message = choices[0].get('message') or {}
        ai_response = message.get('content')
        if not isinstance(ai_response, str):
            raise TypeError('La respuesta de LM Studio no es texto.')

        usage = response_data.get('usage') or {}
        metrics = {
            'latency_ms': round((time.perf_counter() - started_at) * 1000),
            'prompt_tokens': usage.get('prompt_tokens'),
            'completion_tokens': usage.get('completion_tokens'),
            'total_tokens': usage.get('total_tokens'),
            'model': response_data.get('model', 'LM Studio'),
            'finish_reason': choices[0].get('finish_reason')
        }

        chat_history.append({
            "role": "assistant",
            "content": ai_response
        })
        chat_history = chat_history[-MAX_HISTORY_MESSAGES:]
        return jsonify({"response": ai_response, "metrics": metrics})
    except requests.RequestException:
        if chat_history:
            chat_history.pop()
        return jsonify({"response": "Error del servidor local: no se pudo conectar con LM Studio."}), 502
    except (KeyError, IndexError, TypeError, ValueError):
        if chat_history:
            chat_history.pop()
        return jsonify({"response": "LM Studio devolvió una respuesta no válida."}), 502

@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    global chat_history
    chat_history = []
    return jsonify({"status": "success"})

@app.route('/api/model-settings', methods=['GET', 'POST'])
def model_settings_api():
    global model_settings
    if request.method == 'POST':
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "El cuerpo de la petición debe ser JSON."}), 400
        for key in ('vision_enabled', 'thinking_enabled'):
            if key in data:
                if not isinstance(data[key], bool):
                    return jsonify({"error": f"{key} debe ser booleano."}), 400
                model_settings[key] = data[key]
        if 'temperature' in data:
            try:
                temperature = float(data['temperature'])
            except (TypeError, ValueError):
                return jsonify({"error": "La temperatura debe ser un número."}), 400
            if not 0 <= temperature <= 1.5:
                return jsonify({"error": "La temperatura debe estar entre 0 y 1.5."}), 400
            model_settings['temperature'] = temperature
    return jsonify(model_settings)

@app.route('/api/procesar-gmail', methods=['POST'])
def procesar_gmail():
    data = request.get_json(silent=True) or {}
    text = str(data.get('texto', ''))
    encoded_text = urllib.parse.quote(text)
    return jsonify({"status": "success", "url": f"https://mail.google.com/mail/?view=cm&fs=1&body={encoded_text}"})

@app.route('/api/generar-nombre-archivo', methods=['POST'])
def generar_nombre_archivo():
    data = request.get_json(silent=True) or {}
    title = data.get('titulo', 'respuesta_ia')
    filename = secure_filename(f"{title}.md") or 'respuesta_ia.md'
    return jsonify({"status": "success", "filename": filename})

@app.route('/export/<format_type>')
def export_chat(format_type):
    global chat_history
    if format_type not in {'md', 'txt'}:
        return jsonify({"status": "error", "message": "Formato no permitido"}), 400
    CONVERSATIONS_FOLDER.mkdir(parents=True, exist_ok=True)
    filename = f"chat_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{format_type}"
    filepath = CONVERSATIONS_FOLDER / filename

    with filepath.open('w', encoding='utf-8') as f:
        for msg in chat_history:
            role = "USUARIO" if msg['role'] == 'user' else "IA"
            content = msg['content']
            if isinstance(content, list):
                # Extraer texto si es multimodal
                text_parts = [part.get('text', '') for part in content if part.get('type') == 'text']
                has_img = any(part.get('type') == 'image_url' for part in content)
                content_str = " ".join(text_parts) + (" [Imagen Adjunta Procesada]" if has_img else "")
            else:
                content_str = content

            if format_type == 'md':
                f.write(f"### **{role}**\n{content_str}\n\n---\n\n")
            else:
                f.write(f"[{role}]: {content_str}\n\n")

    return send_file(filepath, as_attachment=True, download_name=filename, mimetype='text/markdown' if format_type == 'md' else 'text/plain')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=False)
