-- Handtop: seeking with the right stick (docs/apps/videos.md). The input daemon turns the stick
-- into scroll-wheel steps, more of them the further it is pushed (8.4 a second at full tilt by
-- default, "scroll_speed" in Controls). Each step seeks a share of the video's length, so a
-- short clip and a film take the same push, and the seek speed is capped at MAX_PER_SECOND of
-- the length per second however fast the steps come (Jason, 2026-11-17: speed grows with the
-- push, at most 10 % of the video a second). Each step also shows the on-screen controls.
--
-- A token bucket: it refills at MAX_PER_SECOND and holds at most one step, so a burst of steps
-- (a higher scroll speed in Controls) is spread out instead of jumping further.

local MAX_PER_SECOND = 10.0               -- percent of the length per second, at most
local STEP = MAX_PER_SECOND / 8.4         -- percent per step: full tilt at the default speed = the cap

local tokens, last = STEP, mp.get_time()
local target, target_at = nil, 0           -- where the steps so far are heading

local function seek(dir)
    -- Show the on-screen controls too, as moving the pointer does (Jason, 2026-11-17): the seek
    -- bar shows where the stick is taking you. They hide again after the OSC's hidetimeout.
    mp.commandv("script-message-to", "osc", "osc-show")
    local now = mp.get_time()
    tokens = math.min(STEP, tokens + (now - last) * MAX_PER_SECOND)
    last = now
    local amount = math.min(STEP, tokens)
    local len = mp.get_property_number("duration")
    if amount <= 0.01 or not len or len <= 0 then return end
    tokens = tokens - amount
    -- Absolute seeks to a target the steps add up to: relative seeks issued while the previous
    -- one is still running get merged by mpv and lose steps (measured: 7 % a second instead of
    -- 10). The target starts from the playing position after a pause in the steps.
    if not target or now - target_at > 0.5 then
        target = mp.get_property_number("time-pos") or 0
    end
    target = math.max(0, math.min(len, target + dir * amount * len / 100))
    target_at = now
    -- exact: a step this small seeks back to the same keyframe on files with long keyframe gaps
    mp.commandv("seek", tostring(target), "absolute+exact")
end

mp.add_key_binding(nil, "forward", function() seek(1) end)
mp.add_key_binding(nil, "back", function() seek(-1) end)
