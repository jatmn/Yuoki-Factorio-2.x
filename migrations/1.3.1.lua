-- Revisit saves where 1.2.21 ran before vehicle and corpse inventories were scanned.
local target = prototypes.item["angels-slag"]
if target and not target.hidden then
  require("__Yuoki__/lib/yi-tools")
  yi.lib.migration.global_replace_item("y-slag", "angels-slag")
end
