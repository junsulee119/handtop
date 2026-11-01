-- dmabuf-wayland only accepts dmabuf frames, and mpv falls back to the next VO
-- in the list only when a VO fails to initialise: dmabuf-wayland initialises
-- fine and then rejects software-decoded frames in the filter chain, which
-- leaves the file with audio and no picture ("Could not initialize video
-- chain", "Video: no video"). So keep the zero-copy VO for the codecs the VPU
-- decodes and use the gpu VO for everything else. mpv has no per-codec VO
-- option; this is the hook.
--
-- Caveat: keyed on the codec whitelist, not on the decoder's actual choice. A
-- whitelisted codec that the VPU rejects at runtime still falls back to
-- software and lands back on dmabuf-wayland; fix it when one shows up.
local hw = {}
for c in (mp.get_property("hwdec-codecs") or ""):gmatch("[^,]+") do hw[c] = true end

mp.register_event("file-loaded", function()
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
