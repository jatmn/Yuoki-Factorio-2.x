-- luacheck: globals data
local item = table.deepcopy(data.raw.item["stone"])
item.name = "angels-slag"
data:extend({ item })
