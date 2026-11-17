-- Handtop: mpv's on-screen controller (OSC) in the current theme's colours, sized for the
-- 640x480 screen (docs/apps/videos.md).
--
-- mpv's built-in OSC already has everything a player needs (seek bar, play / pause, previous /
-- next, audio and subtitle tracks, a menu, full screen). This script only gives it Handtop's
-- look: colours and font from the theme.env that rg35xxh-theme renders (never a theme file),
-- with Handtop dark's palette when nothing is rendered, and a larger controller so the buttons
-- are easy to hit with the D-pad pointer. A user's own ~/.config/mpv/script-opts/osc.conf is
-- read by the OSC after this, so it still wins for any option it sets.

local utils = require "mp.utils"

-- Handtop dark, the fallback when no theme is rendered.
local pal = {
    PALETTE_BG = "#1a1e26", PALETTE_SURFACE = "#2b3240", PALETTE_FG = "#e8eaee",
    PALETTE_FG_DIM = "#b8bcc4", PALETTE_ACCENT_FG = "#8fb4ff", FONT_UI = "Noto Sans",
}

local function theme_env()
    local state = os.getenv("XDG_STATE_HOME")
    if not state or state == "" then state = (os.getenv("HOME") or "") .. "/.local/state" end
    return utils.join_path(state, "rg35xxh/theme/theme.env")
end

local function read_theme()
    local f = io.open(theme_env(), "r")
    if not f then return end
    for line in f:lines() do
        local k, v = line:match("^([A-Z0-9_]+)='(.*)'$")
        if k and pal[k] ~= nil and v ~= "" then pal[k] = v end
    end
    f:close()
end

-- "#rrggbb" only (the OSC takes no alpha); anything else keeps the fallback.
local function rgb(v, fallback)
    local hex = v and v:match("^#(%x%x%x%x%x%x)%x?%x?$")
    return hex and ("#" .. hex) or fallback
end

read_theme()

local fg, dim, accent = rgb(pal.PALETTE_FG, "#e8eaee"), rgb(pal.PALETTE_FG_DIM, "#b8bcc4"),
                        rgb(pal.PALETTE_ACCENT_FG, "#8fb4ff")
local opts = {
    background_color = rgb(pal.PALETTE_BG, "#1a1e26"),
    title_color = fg, timecode_color = fg, time_pos_color = fg, buttons_color = fg,
    small_buttonsL_color = fg, small_buttonsR_color = fg, top_buttons_color = fg,
    held_element_color = accent,
    time_pos_outline_color = rgb(pal.PALETTE_BG, "#1a1e26"),
    -- The box layout, scaled up: large buttons, easy to hit with the D-pad pointer.
    layout = "box", boxalpha = "40",
    -- 1.5x, the same whatever the video's resolution: without it the box is ~360 px wide with
    -- 16 px buttons on this screen; with it it fills the width with ~30 px buttons.
    vidscale = "no", scalewindowed = "1.5", scalefullscreen = "1.5",
    seekbarstyle = "bar", hidetimeout = "2500", deadzonesize = "0",
    windowcontrols = "no", unicodeminus = "no",
}

-- Only options the user has not set already (--script-opts on the command line, or mpv.conf).
local have = mp.get_property_native("script-opts") or {}
for k, v in pairs(opts) do
    if have["osc-" .. k] == nil then
        mp.commandv("change-list", "script-opts", "append", "osc-" .. k .. "=" .. v)
    end
end
mp.set_property("osd-font", pal.FONT_UI)

-- The buttons, once per start (overlay/etc/mpv/input.conf has the bindings).
local hinted = false
mp.register_event("file-loaded", function()
    if hinted then return end
    hinted = true
    mp.osd_message("A: play / pause    L1: close\nRight stick: seek    R1 / R2: next / previous", 4)
end)
