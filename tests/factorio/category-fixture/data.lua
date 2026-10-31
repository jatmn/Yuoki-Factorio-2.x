-- luacheck: globals data
-- Split the original categories before Yuoki's final-fixes transformation.
data:extend({ { type = "module-category", name = "yuoki-test-pink" } })
for _, name in ipairs({ "y-pink-module-1", "y-pink-module-2" }) do
  data.raw.module[name].category = "yuoki-test-pink"
end
for _, category in ipairs({ "yuoki-test-pink", "productivity" }) do
  local machine = table.deepcopy(data.raw["assembling-machine"]["assembling-machine-3"])
  machine.name = "yuoki-test-" .. category
  machine.allowed_module_categories = { category }
  data:extend({ machine })
end
