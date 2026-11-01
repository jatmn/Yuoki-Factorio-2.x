-- luacheck: globals data
-- luacheck: read globals yi feature_flags
-- Data-stage regression for the shared atomics recipe API. Any failure stops loading.
local atomics = yi.lib.recipe.atomics

local function same(actual, expected, path)
  if type(actual) ~= "table" or type(expected) ~= "table" then
    assert(actual == expected, path .. ": expected " .. tostring(expected) .. ", got " .. tostring(actual))
    return
  end
  for key, value in pairs(expected) do
    same(actual[key], value, path .. "." .. tostring(key))
  end
  for key, value in pairs(actual) do
    assert(expected[key] ~= nil, path .. "." .. tostring(key) .. ": unexpected " .. tostring(value))
  end
end

-- The prototype that existing positional wrapper calls produced before the shared builder.
local function full_tier(material, material_type, amount, direction, subgroup)
  local material_io = { type = material_type, name = material, amount = amount }
  local unicomp_io = { type = "item", name = "y-unicomp-a2", amount = 1 }
  local down = direction == "down"
  return {
    type = "recipe",
    name = down and "y-ac-" .. material .. "2uc" or "y-ac-uc2" .. material,
    localised_name = {
      down and "recipe-name.y-ac" or "recipe-name.y-ac-uc2",
      { material_type .. "-name." .. material },
    },
    order = "a",
    energy_required = 2,
    enabled = true,
    ingredients = { down and material_io or unicomp_io },
    results = { down and unicomp_io or material_io },
    main_product = down and "y-unicomp-a2" or material,
    subgroup = subgroup,
    categories = { "yuoki-atomics" },
    icons = atomics[material_type .. "_" .. direction](material, 64),
    auto_recycle = false,
    allow_quality = false,
  }
end

-- Runs a registration and checks that exactly the listed recipe IDs were registered.
-- data:extend stores each new table, so replacing an existing ID counts; removals count too.
local function registers(expected_names, register)
  local before = {}
  for name, recipe in pairs(data.raw.recipe) do
    before[name] = recipe
  end
  local results = { register() }
  local changed = {}
  for name, recipe in pairs(data.raw.recipe) do
    if before[name] ~= recipe then
      changed[#changed + 1] = name
    end
  end
  for name in pairs(before) do
    if data.raw.recipe[name] == nil then
      changed[#changed + 1] = name
    end
  end
  table.sort(changed)
  table.sort(expected_names)
  same(changed, expected_names, "registered recipes")
  return table.unpack(results)
end

data:extend({
  { type = "recipe-category", name = "yuoki-test-primitive" },
  { type = "recipe-category", name = "yuoki-test-separation" },
  { type = "surface-property", name = "yuoki-test-industry", default_value = 1 },
})

-- Existing item call from Yuoki itself, then the same positional call re-registering and
-- returning both recipes in order.
local stone_down = full_tier("stone", "item", 20, "down", "j-y-atomics-2")
local stone_up = full_tier("stone", "item", 20, "up", "j-y-atomics-11")
same(data.raw.recipe["y-ac-stone2uc"], stone_down, "y-ac-stone2uc")
same(data.raw.recipe["y-ac-uc2stone"], stone_up, "y-ac-uc2stone")
local first, second = registers({ "y-ac-stone2uc", "y-ac-uc2stone" }, function()
  return atomics.recipes_make_item("stone", 64, 20, 1, "ore")
end)
same(first, stone_down, "recipes_make_item first")
same(second, stone_up, "recipes_make_item second")
assert(data.raw.recipe["y-ac-stone2uc"] == first and data.raw.recipe["y-ac-uc2stone"] == second)

-- Existing fluid call with a subgroup.
local water_down = full_tier("water", "fluid", 100, "down", "j-y-atomics-7")
local water_up = full_tier("water", "fluid", 100, "up", "j-y-atomics-14")
first, second = registers({ "y-ac-water2uc", "y-ac-uc2water" }, function()
  return atomics.recipes_make_fluid("water", 64, 100, 1, "fluid")
end)
same(first, water_down, "recipes_make_fluid first")
same(second, water_up, "recipes_make_fluid second")
assert(data.raw.recipe["y-ac-water2uc"] == first and data.raw.recipe["y-ac-uc2water"] == second)

-- One-way primitive stone -> solid UC in a caller-selected category.
-- Factorio rejects recipe surface_conditions unless space travel is enabled (e.g. Space Age).
local surface_conditions
if feature_flags.space_travel then
  surface_conditions = { { property = "yuoki-test-industry", min = 1, max = 1 } }
end
local primitive = registers({ "yuoki-test-stone-to-uc" }, function()
  return atomics.make_recipe("stone", "down", {
    size = 64,
    amount = 40,
    fields = {
      name = "yuoki-test-stone-to-uc",
      categories = { "yuoki-test-primitive" },
      energy_required = 8,
      enabled = false,
      subgroup = "j-y-atomics-2",
      order = "z",
      localised_name = { "recipe-name.yuoki-test-stone-to-uc" },
      localised_description = { "recipe-description.yuoki-test-stone-to-uc" },
      surface_conditions = surface_conditions,
      allow_productivity = false,
    },
  })
end)
same(data.raw.recipe["yuoki-test-stone-to-uc"], primitive, "registered primitive")
local expected_primitive = {
  type = "recipe",
  name = "yuoki-test-stone-to-uc",
  localised_name = { "recipe-name.yuoki-test-stone-to-uc" },
  localised_description = { "recipe-description.yuoki-test-stone-to-uc" },
  order = "z",
  energy_required = 8,
  enabled = false,
  ingredients = { { type = "item", name = "stone", amount = 40 } },
  results = { { type = "item", name = "y-unicomp-a2", amount = 1 } },
  main_product = "y-unicomp-a2",
  subgroup = "j-y-atomics-2",
  categories = { "yuoki-test-primitive" },
  surface_conditions = surface_conditions,
  icons = atomics.item_down("stone", 64),
  auto_recycle = false,
  allow_quality = false,
  allow_productivity = false,
}
same(primitive, expected_primitive, "primitive stone")

-- Liquid UC -> water: directional icon, fluid input kept, no reverse recipe.
local water = registers({ "yuoki-test-water" }, function()
  return atomics.make_recipe("water", "up", {
    material_type = "fluid",
    amount = 100,
    unicomp = "y-liquid-uc2",
    unicomp_type = "fluid",
    fields = { name = "yuoki-test-water", categories = { "yuoki-test-separation" }, enabled = false },
  })
end)
same(water.ingredients, { { type = "fluid", name = "y-liquid-uc2", amount = 1 } }, "water ingredients")
same(water.results, { { type = "fluid", name = "water", amount = 100 } }, "water results")
same(water.main_product, "water", "water main_product")
same(water.categories, { "yuoki-test-separation" }, "water categories")
same(water.icons, atomics.fluid_up("water"), "water icons")

-- Opting in left the full-tier recipes for the same materials unchanged.
same(data.raw.recipe["y-ac-stone2uc"], stone_down, "y-ac-stone2uc after primitive")
same(data.raw.recipe["y-ac-uc2stone"], stone_up, "y-ac-uc2stone after primitive")
same(data.raw.recipe["y-ac-water2uc"], water_down, "y-ac-water2uc after primitive")
same(data.raw.recipe["y-ac-uc2water"], water_up, "y-ac-uc2water after primitive")

-- An invalid direction raises before registering, adding, or replacing anything.
local ok = registers({}, function()
  return pcall(atomics.make_recipe, "stone", "sideways")
end)
assert(not ok, "invalid direction must fail")
log("ATOMICS_PASS")
