# Tkinter macOS Native Pinch-to-Zoom

[日本語版はこちら](README.md)

Since native pinch-to-zoom is not supported in standard Tkinter on macOS, I collaborated with Gemini to create this solution.
All files, including this README.md, were developed in partnership with Gemini. It has been confirmed to work accurately in my macOS environment (26.4 / 25E246).
If it doesn't work for you, please let me know via Issues, and I may be able to update it.

This is a reference implementation for achieving macOS standard **native pinch-to-zoom (magnification gestures)** within a Tkinter application.

## 🌟 Overview

In standard Tkinter (Python), macOS-specific gesture events (`NSEventTypeMagnify`) cannot be captured using the built-in `bind` method.

This project accesses the OS-level event stream via **PyObjC** and safely bridges the data to the Tkinter event loop. This enables smooth, native-feeling pinch operations identical to standard macOS applications.

## 🖱 Device & Operation Interpretation (Internal Logic)

The program handles differences in physical devices and OS behaviors through the following logic to provide a consistent user experience.

| Category | Physical Operation | Target OS | Internal Event Interpretation | Implemented Feature |
| :--- | :--- | :--- | :--- | :--- |
| **Free Pan** | Left-click Drag | All | `<B1-Motion>` | Grab and move image |
| | 3-finger Drag | Mac | `<B1-Motion>` (Emulated by OS) | Grab and move image |
| **Smooth Scroll** | 2-finger Swipe | All | `<MouseWheel>` / `<Shift-MouseWheel>` | Scroll via ratio (`moveto`) |
| | Mouse Wheel Scroll | All | `<MouseWheel>` | Scroll via ratio (`moveto`) |
| | Tilt Wheel (Left/Right) | All | `<Shift-MouseWheel>` | Horizontal Scroll |
| **Zoom** | **2-finger Pinch** | **Mac** | **NSEventTypeMagnify (via AppKit)** | **Native Pinch Zoom** |
| | Cmd + Wheel Scroll | Mac | `<MouseWheel>` + State(0x8) | Cursor-centered Zoom |
| | Ctrl + Wheel Scroll | Win | `<MouseWheel>` + State(0x4) | Cursor-centered Zoom |

## ⌨️ Event Mapping Details

| Tkinter Event / Signal Source | Condition (State/System) | Target OS | Physical User Action | Executed Function |
| :--- | :--- | :--- | :--- | :--- |
| **`<ButtonPress-1>`** | None | All | Left Click / 1-finger Tap | `canvas.scan_mark` |
| **`<B1-Motion>`** | None | All | Left Drag / 3-finger Drag | `canvas.scan_dragto` |
| **`<MouseWheel>`** | `is_zoom = False` | All | Vertical Scroll / 2-finger Swipe (Up/Down) | `apply_move` |
| | `is_zoom = True` | All | Cmd(Mac) or Ctrl(Win) + Wheel Scroll | `apply_zoom` |
| **`<Shift-MouseWheel>`** | None | All | Tilt Left/Right / 2-finger Swipe (Left/Right) | `apply_move` |
| **`NSEventTypeMagnify`** | None (AppKit) | **Mac** | **2-finger Pinch (In/Out)** | **`apply_zoom`** |
| **`<Enter>`** | None | All | Mouse entering Canvas | `canvas.focus_set` |

## 🚀 Key Features

- **Native Pinch Operation**: Intuitive zooming using the trackpad.
- **Intelligent Zoom**: Zoom in/out relative to the current mouse cursor position.
- **Thread-Safe Design**: Uses `queue.Queue` to prevent race conditions (GIL crashes) between OS threads and Tkinter.
- **High-Performance Rendering**: Adaptive rendering using low-quality (`NEAREST`) during operation and switching to high-quality (`BILINEAR`) once stopped.
- **Comprehensive Controls**: Supports 2-finger scrolling, drag-to-pan, and Command+Wheel zooming.

## 🛠 Technical Background

1. **AppKit Event Monitor**: Uses `addLocalMonitorForEventsMatchingMask` to directly catch gesture events that Tkinter normally discards.
2. **Complete Thread Isolation**: Signals from the OS system thread are stored in a queue and processed by the Tkinter main thread using polling (`after` method) for safe UI updates.
3. **OS-Specific Log Suppression**: Suppresses unnecessary system error logs such as `IMKCFRunLoopWakeUpReliable` (common on macOS Sequoia) to keep the development console clean.

## 📦 Requirements

- macOS (Intel / Apple Silicon) / Windows (Mouse operations only)
- Python 3.10+
- Dependencies: `Pillow`, `pyobjc` (macOS only)

## ⚡ Quick Start

```bash
# Clone the repository
git clone [https://github.com/masaoikawa/tkinter-macos-pinch.git](https://github.com/masaoikawa/tkinter-macos-pinch.git)
cd tkinter-macos-pinch

# Install dependencies and run (when using uv)
uv sync
uv run src/main.py
```

## 📄 License
This project is licensed under the **MIT License**.
For more details, please see the [LICENSE](LICENSE) file.

Copyright (c) 2026 masaoikawa
