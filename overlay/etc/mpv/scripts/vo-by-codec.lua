-- dmabuf-wayland only accepts dmabuf frames, and mpv falls back to the next VO
-- in the list only when a VO fails to initialise: dmabuf-wayland initialises
-- fine and then rejects software-decoded frames in the filter chain, which
-- leaves the file with audio and no picture ("Could not initialize video
-- chain", "Video: no video"). So keep the zero-copy VO for the codecs the VPU
-- decodes and use the gpu VO for everything else. mpv has no per-codec VO
-- option; this is the hook. Run it before the decoder is opened: switching the
-- VO at file-loaded reinitialises the video chain after the first keyframe,
-- which reopens the decoder mid-stream and breaks software codecs (dav1d fails
-- every frame after the reopen).
--
-- Caveat: keyed on the codec whitelist, not on the decoder's actual choice. A
-- whitelisted codec that the VPU rejects at runtime still falls back to
-- software and lands back on dmabuf-wayland; fix it when one shows up.
local hw = {}
for c in (mp.get_property("hwdec-codecs") or ""):gmatch("[^,]+") do hw[c] = true end

-- An explicit single VO is a choice, not the shipped two-entry default this
-- script manages: "mpv --vo=gpu" (or a user's own vo=) must be left alone.
-- Read once at load, because the script itself changes vo while it runs.
local managed = (mp.get_property("vo") or ""):find("dmabuf%-wayland") ~= nil

mp.add_hook("on_preloaded", 50, function()
  if not managed then return end
  for i = 0, (mp.get_property_number("track-list/count") or 0) - 1 do
    local t = "track-list/" .. i
    if mp.get_property(t .. "/type") == "video" then
      local want = hw[mp.get_property(t .. "/codec") or ""] and "dmabuf-wayland,gpu" or "gpu"
      mp.msg.verbose("video codec " .. tostring(mp.get_property(t .. "/codec")) .. " -> vo=" .. want)
      mp.set_property("vo", want)
      return
    end
  end
end)
