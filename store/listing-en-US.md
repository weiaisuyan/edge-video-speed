# Edge Add-ons store listing · English (en-US)

## Name
Video Speed Control (on-page button)

## Short description
A floating speed button drawn inside the page — tap it to change video playback speed. Custom presets, per-site memory, and it works in installed app windows too.

## Detailed description

Unlike extensions that live only in the browser toolbar, **this button is rendered inside the page**, so it also works in windows opened with Edge's "Install as app" (Bilibili, Weibo, Xiaohongshu, YouTube, ...). No need to switch back to the browser.

**Features**
- On-page floating button (top-right by default) showing the current speed; click to open a menu of presets
- Custom presets from 0.1x to 10x (up to 12); fine-tune with −/+ or the slider (live value shown under the slider)
- Per-site speed memory (Bilibili 1.5x, YouTube 2x, no interference); 1x is the default and is never recorded
- **Plays nice with the site's own player**: change the speed in the site's built-in player and the extension reads and remembers it instead of fighting back. Your chosen speed is only re-applied right after the player loads a new video
- Drag to move: hold Ctrl and drag the button; position is remembered as a percentage of the window
- Appearance: 16 styles (solid / gradient / glass / glow), size 60%–500%, adjustable corner radius, separate hover and idle opacity (the popup menu always stays fully opaque)
- Works in fullscreen playback (the button is moved inside the fullscreen player). Optional: hide the button in fullscreen instead — the player's fullscreen, a site's own "web fullscreen" (Bilibili and friends) and browser fullscreen (F11) all hide it, and it comes back the moment you exit
- Hotkeys: Ctrl+Shift+> faster / Ctrl+Shift+< slower / Ctrl+Shift+0 reset
- Show only on pages with video, or on every page; per-site exclusion list
- Export / import settings

**Known limits (browser security, same for every extension)**
- `edge://` pages, the add-ons store, and the built-in PDF viewer
- Apps that are not rendered by Edge (e.g. a standalone desktop client) cannot be controlled

## Category
Productivity

## Search terms
video speed / playback speed / speed control / video accelerator / floating button

## Privacy
No data is collected. The extension only uses `chrome.storage.local` to keep your settings (presets, button position, style, per-site speeds) on your device. No network calls, no remote code.
