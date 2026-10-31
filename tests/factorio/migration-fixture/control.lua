-- luacheck: globals script game storage prototypes
local stop_at
local function finish()
  if game.is_multiplayer() then
    game.tick_paused = true
  else
    script.finish_test(true)
  end
end

script.on_init(function()
  local surface = game.surfaces[1]
  surface.request_to_generate_chunks({ 0, 0 }, 2)
  surface.force_generate_chunk_requests()
  storage.quality = prototypes.quality.legendary and "legendary" or "normal"
  storage.entities = {}
  storage.stage = "old"
  for i, name in ipairs({ "car", "spidertron", "character-corpse" }) do
    local entity = assert(surface.create_entity({
      name = name == "character-corpse" and "character" or name,
      position = { i * 12, 0 },
      force = "player",
    }))
    local inventory = name == "character-corpse" and entity.get_main_inventory()
      or entity.get_inventory(name == "car" and defines.inventory.car_trunk or defines.inventory.spider_trunk)
    inventory[1].set_stack({ name = "y-slag", count = 100 })
    inventory[2].set_stack({ name = "y-slag", count = 73, quality = storage.quality })
    inventory[3].set_stack({ name = "iron-plate", count = 7, quality = storage.quality })
    if prototypes.item["angels-slag"] then
      inventory[4].set_stack({ name = "angels-slag", count = 11 })
    end
    if name == "character-corpse" then
      entity.die()
      entity = assert(surface.find_entities_filtered({ type = "character-corpse" })[1])
    end
    table.insert(storage.entities, entity)
  end
end)

script.on_event(defines.events.on_tick, function(event)
  if stop_at then
    if event.tick >= stop_at then
      finish()
    end
    return
  end
  local totals = {}
  local function count(stack)
    if stack.valid_for_read then
      local key = stack.name .. "/" .. stack.quality.name
      totals[key] = (totals[key] or 0) + stack.count
    end
  end
  for _, entity in ipairs(storage.entities) do
    for i = 1, entity.get_max_inventory_index() do
      local inventory = entity.get_inventory(i)
      if inventory then
        for j = 1, #inventory do
          count(inventory[j])
        end
      end
    end
  end
  for _, ground in pairs(game.surfaces[1].find_entities_filtered({ type = "item-entity" })) do
    count(ground.stack)
  end
  local target = prototypes.item["angels-slag"]
  local converted = storage.stage ~= "old" and target and not target.hidden
  local expected = {}
  local function expect(name, quality, amount)
    local key = name .. "/" .. quality
    expected[key] = (expected[key] or 0) + amount
  end
  local slag = converted and "angels-slag" or "y-slag"
  expect(slag, "normal", 300)
  expect(slag, storage.quality, 219)
  expect("iron-plate", storage.quality, 21)
  if target then
    expect("angels-slag", "normal", 33)
  end
  if storage.stage == "reload" then
    expect("y-slag", "normal", 1)
  end
  for key, amount in pairs(expected) do
    assert(
      totals[key] == amount,
      storage.stage .. ": " .. key .. " expected " .. amount .. ", got " .. (totals[key] or 0)
    )
    totals[key] = nil
  end
  assert(next(totals) == nil, "Unexpected items after migration")
  log("YUOKI SAVED MIGRATION PASS: " .. storage.stage .. ", quality=" .. storage.quality)
  if storage.stage == "reload" then
    finish()
    return
  end
  if storage.stage == "old" then
    storage.stage = "upgrade"
    game.server_save("yuoki-old-migration-applied")
  else
    assert(storage.entities[1].get_inventory(defines.inventory.car_trunk).insert({ name = "y-slag", count = 1 }) == 1)
    storage.stage = "reload"
    game.server_save("yuoki-followup-applied")
  end
  stop_at = event.tick + 2
end)
