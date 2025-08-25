import mido
from mido import Message
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
from PIL import Image, ImageDraw, ImageFont
import subprocess
import time
import tkinter as tk
from tkinter import ttk

def close_elgato_software():
    try:
        subprocess.run(
            ["taskkill", "/f", "/im", "StreamDeck.exe"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)
    except:
        pass

close_elgato_software()

available_ports = mido.get_output_names()
MIDI_PORT_NAME = next((p for p in available_ports if p.startswith("StreamDeckMIDI")), None)
if not MIDI_PORT_NAME:
    raise RuntimeError("No StreamDeckMIDI port found. Create one in loopMIDI.")
outport = mido.open_output(MIDI_PORT_NAME)
print("Using MIDI port:", MIDI_PORT_NAME)

decks = DeviceManager().enumerate()
if not decks:
    raise RuntimeError("No Stream Deck found.")

root = tk.Tk()
root.title("Stream Deck MIDI Controller")
gui_buttons = {}
frame = tk.Frame(root)
frame.pack(padx=10, pady=10)
cols = 8

selected_deck = tk.StringVar()
deck_instance = None

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
def note_name(midi_note):
    octave = (midi_note // 12) - 1
    name = NOTE_NAMES[midi_note % 12]
    return f"{name}{octave}"

def generate_note_colors(count, start_note=60):
    base_colors = ["#FF4C4C", "#FF9F4C", "#FFD24C", "#9FFF4C", "#4CFF4C", "#4CFF9F", "#4CFFFF", "#4C9FFF"]
    return {start_note + i: base_colors[i % len(base_colors)] for i in range(count)}

def render_key_image(deck, text, base_color="#1a1a1a", pressed=False):
    fmt = deck.key_image_format()
    key_w, key_h = fmt["size"]
    color = base_color
    if pressed:
        r, g, b = tuple(int(base_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        r = int(r * 0.5)
        g = int(g * 0.5)
        b = int(b * 0.5)
        color = f"#{r:02X}{g:02X}{b:02X}"
    image = Image.new("RGB", (key_w, key_h), color)
    draw = ImageDraw.Draw(image)
    radius = 12
    draw.rounded_rectangle([(0, 0), (key_w - 1, key_h - 1)], radius=radius, outline="gray", width=3)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except:
        font = ImageFont.load_default()
    if hasattr(font, "getbbox"):
        bbox = font.getbbox(text)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    else:
        text_w, text_h = font.getsize(text)
    draw.text(((key_w - text_w) // 2, (key_h - text_h) // 2), text, fill="white", font=font)
    highlight = Image.new("RGBA", (key_w, key_h // 4), (255, 255, 255, 30))
    image.paste(highlight, (0, 0), highlight)
    return PILHelper.to_native_format(deck, image)

def darken_color(hex_color, factor=0.5):
    r, g, b = tuple(int(hex_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    r = int(r * factor)
    g = int(g * factor)
    b = int(b * factor)
    return f"#{r:02X}{g:02X}{b:02X}"

def key_change(deck, key, state):
    if key in BUTTON_TO_NOTE:
        note = BUTTON_TO_NOTE[key]
        vel = BUTTON_TO_VELOCITY[key]
        base_color = NOTE_COLORS.get(note, "#1a1a1a")
        if state:
            outport.send(Message('note_on', note=note, velocity=vel))
            deck.set_key_image(key, render_key_image(deck, note_name(note), base_color, pressed=True))
            gui_buttons[key].config(bg=darken_color(base_color, 0.5))
        else:
            outport.send(Message('note_off', note=note, velocity=vel))
            deck.set_key_image(key, render_key_image(deck, note_name(note), base_color, pressed=False))
            gui_buttons[key].config(bg=base_color)

def select_deck(event=None):
    global deck_instance, BUTTON_TO_NOTE, BUTTON_TO_VELOCITY, NOTE_COLORS
    if deck_instance:
        deck_instance.reset()
        deck_instance.close()
    idx = int(selected_deck.get().split(':')[0])
    deck_instance = decks[idx]
    deck_instance.open()
    deck_instance.reset()
    BUTTON_TO_NOTE = {i: 60 + i for i in range(deck_instance.key_count())}
    BUTTON_TO_VELOCITY = {i: 100 for i in range(deck_instance.key_count())}
    NOTE_COLORS = generate_note_colors(deck_instance.key_count())
    for key, note in BUTTON_TO_NOTE.items():
        deck_instance.set_key_image(key, render_key_image(deck_instance, note_name(note), NOTE_COLORS[note]))
    deck_instance.set_key_callback(key_change)
    for widget in frame.winfo_children():
        widget.destroy()
    for i in range(deck_instance.key_count()):
        note = BUTTON_TO_NOTE[i]
        btn = tk.Button(frame, text=note_name(note), width=6, height=3, bg=NOTE_COLORS[note],
                        command=lambda i=i: key_change(deck_instance, i, True))
        btn.grid(row=i // 8, column=i % 8, padx=2, pady=2)
        gui_buttons[i] = btn

deck_options = [f"{i}: {d.deck_type()}" for i, d in enumerate(decks)]
deck_selector = ttk.Combobox(root, values=deck_options, textvariable=selected_deck, state="readonly")
deck_selector.pack(pady=5)
deck_selector.bind("<<ComboboxSelected>>", select_deck)
selected_deck.set(deck_options[0])
select_deck()

print("Stream Deck MIDI controller running. Press buttons or use GUI.")
root.mainloop()

if deck_instance:
    deck_instance.reset()
    deck_instance.close()
