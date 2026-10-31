-- Yuoki productivity behavior, originally by Michael Cowgill (ChurchOrganist), 2020.
-- Factorio 2.1 uses recipe eligibility and module categories instead of limitations.
if settings.startup["yuoki-prod-mod-behaviour"].value then
  return
end

local unrestricted = {}
local category_additions = {}
local function inherit_category(original, added)
  category_additions[original] = category_additions[original] or {}
  category_additions[original][added] = true
end
for _, name in ipairs({ "y-pink-module-1", "y-pink-module-2", "y-pink-module-3", "y_modul_science" }) do
  local module = data.raw.module[name]
  -- Keep original machine permissions distinct, even when other mods split them.
  local category = "yuoki-unrestricted-" .. module.category
  if not unrestricted[category] then
    data:extend({ { type = "module-category", name = category } })
    unrestricted[category] = true
  end
  inherit_category(module.category, category)
  module.category = category
end

-- A mixed category must not make speed/efficiency modules lose recipe access.
local productive, nonproductive = {}, {}
for _, module in pairs(data.raw.module) do
  if not unrestricted[module.category] then
    local categories = (module.effect.productivity or 0) > 0 and productive or nonproductive
    categories[module.category] = true
  end
end
local restricted = {}
for category in pairs(productive) do
  local target = category
  if nonproductive[category] then
    target = "yuoki-restricted-" .. category
    data:extend({ { type = "module-category", name = target } })
    inherit_category(category, target)
    for _, module in pairs(data.raw.module) do
      if module.category == category and (module.effect.productivity or 0) > 0 then
        module.category = target
      end
    end
  end
  restricted[target] = true
end

-- Preserve explicit machine/recipe allowlists when a category is split.
for _, prototypes in pairs(data.raw) do
  for _, prototype in pairs(prototypes) do
    if prototype.allowed_module_categories then
      local allowed = {}
      for _, category in pairs(prototype.allowed_module_categories) do
        allowed[category] = true
        for addition in pairs(category_additions[category] or {}) do
          allowed[addition] = true
        end
      end
      prototype.allowed_module_categories = {}
      for category in pairs(allowed) do
        table.insert(prototype.allowed_module_categories, category)
      end
      table.sort(prototype.allowed_module_categories)
    end
  end
end

for _, recipe in pairs(data.raw.recipe) do
  if not recipe.allow_productivity then
    local allowed = {}
    local categories = recipe.allowed_module_categories
    if not categories then
      categories = {}
      for category in pairs(data.raw["module-category"]) do
        table.insert(categories, category)
      end
    end
    for _, category in pairs(categories) do
      if not restricted[category] and not unrestricted[category] then
        table.insert(allowed, category)
      end
    end
    recipe.allow_productivity = true
    recipe.allowed_module_categories = allowed
  end
  if recipe.allowed_module_categories then
    local present = {}
    for _, category in pairs(recipe.allowed_module_categories) do
      present[category] = true
    end
    for category in pairs(unrestricted) do
      if not present[category] then
        table.insert(recipe.allowed_module_categories, category)
      end
    end
    table.sort(recipe.allowed_module_categories)
  end
end
