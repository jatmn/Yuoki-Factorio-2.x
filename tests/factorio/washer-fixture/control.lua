-- luacheck: globals script game storage prototypes helpers
local names = { "y-dirtwasher", "y_mc_dirtwasher" }
local directions = { defines.direction.north, defines.direction.east, defines.direction.south, defines.direction.west }
local right = {
  [defines.direction.north] = { x = 1, y = 0 },
  [defines.direction.east] = { x = 0, y = 1 },
  [defines.direction.south] = { x = -1, y = 0 },
  [defines.direction.west] = { x = 0, y = -1 },
}

local function check_output_port(entity, pipe)
  local axis = right[entity.direction]
  local dx = pipe.entity.position.x - entity.position.x
  local dy = pipe.entity.position.y - entity.position.y
  -- Check physical positions, independently of recipe filters and storage indexes.
  if -dx * axis.y + dy * axis.x ~= 2 then
    return false
  end
  local side = dx * axis.x + dy * axis.y
  assert(side == 1 or side == -1, "unexpected physical output port")
  local expected = side == 1 and "y-con_water" or "y-mechanical-force"
  local expected_amount = side == 1 and 20 or 9
  local delivered = 0
  for name, amount in pairs(pipe.entity.get_fluid_contents()) do
    assert(name == expected, "wrong fluid at physical output port: expected " .. expected)
    delivered = delivered + amount
  end
  assert(delivered > 0, "no fluid reached physical output port")
  local buffered = entity.get_fluid(pipe.storage_index)
  if buffered then
    assert(buffered.name == expected, "wrong fluid in output buffer")
    delivered = delivered + buffered.amount
  end
  assert(math.abs(delivered - expected_amount) < 0.001, "wrong amount at physical output port")
  return true
end

local function qualities()
  return prototypes.quality.rare and { "normal", "rare" } or { "normal" }
end

local function create(name, quality, direction)
  storage.count = storage.count + 1
  local position = { (storage.count % 16) * 12, math.floor(storage.count / 16) * 12 }
  return assert(game.surfaces["washer-fixture"].create_entity({
    name = name,
    position = position,
    direction = direction,
    quality = quality,
    force = "player",
  }))
end

local function pipes(entity)
  local result = {}
  for i = 1, entity.fluids_count do
    for _, connection in ipairs(entity.get_fluid_box_pipe_connections(i)) do
      local pipe =
        assert(entity.surface.create_entity({ name = "pipe", position = connection.target_position, force = "player" }))
      result[#result + 1] = { entity = pipe, storage_index = i }
    end
  end
  return result
end

local function snapshot(test)
  local entity = test.entity
  local recipe, quality = entity.get_recipe()
  local result = {
    recipe = recipe.name,
    quality = quality.name,
    entity_quality = entity.quality.name,
    fluids_count = entity.fluids_count,
  }
  for _, index in ipairs({
    defines.inventory.crafter_input,
    defines.inventory.crafter_output,
    defines.inventory.crafter_modules,
  }) do
    for _, stack in ipairs(entity.get_inventory(index).get_contents()) do
      result[index .. ":" .. stack.name .. ":" .. stack.quality] = stack.count
    end
  end
  local entities = { entity }
  for _, pipe in ipairs(test.pipes) do
    entities[#entities + 1] = pipe.entity
  end
  for n, owner in ipairs(entities) do
    for i = 1, owner.fluids_count do
      local prefix = n .. ":fluid:" .. i .. ":"
      local fluid = owner.get_fluid(i)
      result[prefix .. "capacity"] = owner.get_fluid_capacity(i)
      if fluid then
        result[prefix .. "name"] = fluid.name
        result[prefix .. "amount"] = fluid.amount
        result[prefix .. "temperature"] = fluid.temperature
      end
    end
  end
  return result
end

local function power(entity)
  local pos = entity.position
  local source = entity.surface.create_entity({
    name = "electric-energy-interface",
    position = { pos.x + 4, pos.y + 4 },
    force = "player",
  })
  source.power_production = 1000000000
  source.power_usage = 0
  entity.surface.create_entity({ name = "substation", position = { pos.x + 4, pos.y }, force = "player" })
end

script.on_init(function()
  storage.count = 0
  storage.legacy = {}
  local surface = game.create_surface("washer-fixture", { width = 512, height = 512 })
  surface.request_to_generate_chunks({ 96, 96 }, 6)
  surface.force_generate_chunk_requests()
  for _, name in ipairs(names) do
    for _, quality in ipairs(qualities()) do
      for _, direction in ipairs(directions) do
        for recipe_name, recipe in pairs(prototypes.recipe) do
          if recipe_name ~= "ye_neutralisatzion" and recipe.categories[1] == "yuoki-archaeology-wash" then
            local entity = create(name, quality, direction)
            entity.set_recipe(recipe_name, quality)
            assert(entity.get_recipe(), recipe_name)
            entity.disabled_by_script = true
            local test = { entity = entity, pipes = pipes(entity) }
            for _, ingredient in ipairs(recipe.ingredients) do
              if ingredient.type == "item" then
                assert(
                  entity
                    .get_inventory(defines.inventory.crafter_input)
                    .insert({ name = ingredient.name, count = ingredient.amount, quality = quality })
                    == ingredient.amount
                )
              end
            end
            assert(entity.get_module_inventory().insert({ name = "speed-module", count = 1, quality = quality }) == 1)
            for _, product in ipairs(recipe.products) do
              if product.type == "item" then
                assert(
                  entity
                    .get_inventory(defines.inventory.crafter_output)
                    .insert({ name = product.name, count = 2, quality = quality }) == 2
                )
              end
            end
            for i = 1, entity.fluids_count do
              local filter = entity.get_fluid_filter(i)
              assert(
                entity.set_fluid(i, { name = filter.name, amount = entity.get_fluid_capacity(i), temperature = 75 }) > 0
              )
            end
            for _, pipe in ipairs(test.pipes) do
              local filter = entity.get_fluid_filter(pipe.storage_index)
              assert(pipe.entity.insert_fluid({ name = filter.name, amount = 50, temperature = 75 }) == 50)
            end
            test.before = snapshot(test)
            storage.legacy[#storage.legacy + 1] = test
          end
        end
      end
    end
  end
  log("WASHER_SEED " .. #storage.legacy)
end)

script.on_configuration_changed(function()
  for _, test in ipairs(storage.legacy) do
    local after = snapshot(test)
    for key, value in pairs(test.before) do
      assert(
        after[key] == value or (type(value) == "number" and math.abs(after[key] - value) < 0.001),
        key .. " changed"
      )
    end
    for key in pairs(after) do
      assert(test.before[key] ~= nil, key .. " appeared")
    end
    for i = 1, test.entity.fluids_count do
      assert(#test.entity.get_fluid_box_pipe_connections(i) == 2, "single-fluid recipe lost a port")
      assert(#test.entity.get_fluid_box_neighbours(i) == 2, "single-fluid recipe lost a connected pipe")
    end
  end
  log("WASHER_PRESERVED " .. #storage.legacy .. " recipes, inventories, capacities, fluids and pipe connections")
  storage.acid = {}
  for _, name in ipairs(names) do
    for _, quality in ipairs(qualities()) do
      for _, direction in ipairs(directions) do
        local entity = create(name, quality, direction)
        entity.set_recipe("ye_neutralisatzion", quality)
        assert(entity.get_recipe(), "acid neutralization rejected")
        assert(entity.fluids_count == 4, "acid neutralization needs four independent storages")
        assert(entity.set_fluid(1, { name = "water", amount = 1 }) == 0, "acid input accepts water")
        local test = { entity = entity, pipes = pipes(entity) }
        assert(
          entity
            .get_inventory(defines.inventory.crafter_input)
            .insert({ name = "ye_substrat", count = 40, quality = quality }) == 40
        )
        for _, pipe in ipairs(test.pipes) do
          local filter = entity.get_fluid_filter(pipe.storage_index)
          if filter.name == "water" or filter.name == "sulfuric-acid" then
            local amount = filter.name == "water" and 100 or 9
            assert(pipe.entity.insert_fluid({ name = filter.name, amount = amount }) == amount)
          end
        end
        power(entity)
        storage.acid[#storage.acid + 1] = test
      end
    end
  end
  storage.finish_tick = game.tick + 300
end)

script.on_event(defines.events.on_tick, function(event)
  if not storage.finish_tick or event.tick < storage.finish_tick then
    return
  end
  for _, test in ipairs(storage.acid) do
    assert(test.entity.products_finished == 1, "acid recipe did not complete exactly once")
    local totals = test.entity.get_fluid_contents()
    local outputs = 0
    for _, pipe in ipairs(test.pipes) do
      if check_output_port(test.entity, pipe) then
        outputs = outputs + 1
      end
      for name, amount in pairs(pipe.entity.get_fluid_contents()) do
        totals[name] = (totals[name] or 0) + amount
      end
    end
    assert(outputs == 2, "missing physical output port")
    assert(math.abs((totals["y-con_water"] or 0) - 20) < 0.001, "contaminated-water count")
    assert(math.abs((totals["y-mechanical-force"] or 0) - 9) < 0.001, "mechanical-force count")
    assert((totals.water or 0) < 0.001 and (totals["sulfuric-acid"] or 0) < 0.001, "inputs not consumed")
  end
  log("WASHER_PASS " .. #storage.acid .. " acid recipes using physical pipes")
  script.finish_test(true)
end)
