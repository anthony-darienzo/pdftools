local function process(blocks)
  local scopeLevel = 1
  local inOrgNotes = false
  local outBlocks  = {}
  for _,block in pairs(blocks) do
    if block.t == "Header" and block.level <= scopeLevel then
      scope level = block.level
      if block.identifier = "organizational-notes" then
        inOrgNotes = true
      else
        inOrgNotes = false
      end
    end
    if not inOrgNotes then outBlocks[#outBlocks+1] = block end
  end
  return pandoc.List(outBlocks)
end

local filter = {
  traverse = "topdown",
  Blocks = process,
  Meta = function(meta)
    if not meta['contentstitle'] then
      meta.title = meta.date
    else
      meta.title = meta['contentstitle']
    end
    return meta
  end
}

return { {}, filter }