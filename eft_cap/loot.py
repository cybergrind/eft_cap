import pathlib
from pprint import pprint
import logging

import numpy as np

from eft_cap import ParsingError
from eft_cap.bin_helpers import ByteStream
from functools import lru_cache
import json

log = logging.getLogger('loot')
DB_ITEMS = pathlib.Path('LeakedServer/db/items')
PRICES = DB_ITEMS / '../templates/items'
DB_EXISTS = DB_ITEMS.exists()
ID_LEN = len('5888988e24597752fe43a6fa')


class LootParsingError(ParsingError):
    pass


@lru_cache(maxsize=None)
def get_description(template_id):
    if len(template_id) != ID_LEN:
        raise LootParsingError(f'Wrong TemplateID: {template_id!r}')

    if not DB_EXISTS:
        return {'name': template_id}
    p_name = f'{template_id}.json'
    f_item = DB_ITEMS.joinpath(p_name)
    if not f_item.exists():
        return {'name': template_id}
    out = {}
    j_data = json.loads(f_item.read_text(encoding='utf8'))
    out['name'] = j_data.get('_name')
    p_item = PRICES.joinpath(p_name)
    if p_item.exists():
        pj_data = json.loads(p_item.read_text())
        out['price'] = pj_data.get('Price', 0)
    return out


def read_item_descriptor(d: ByteStream, ctx):
    return {
        'id': d.read_string(),
        'contained_item': read_item(d, ctx),
    }


def read_grid(d, ctx):
    out = {
        'id': d.read_string(),
        'items': [],
    }
    num = d.read_u32()
    for i in range(num):
        out['items'].append(read_item_in_grid(d, ctx))
    return out


def read_stack_slot(d: ByteStream, ctx):
    ret = {
        'id': d.read_string(),
        'items': [],
    }
    num_items = d.read_u32()
    for item in range(num_items):
        ret['items'].append(read_item(d, ctx))
    return ret


def recurse_item(item, func, nesting=0, ctx={}):
    skip_recurse = func(item, nesting=nesting, ctx=ctx)
    if skip_recurse:
        return

    for slot in item['slots']:
        recurse_item(
            slot['contained_item'], func, nesting=nesting + 1, ctx={**ctx, 'slot': slot}
        )
    for grid in item['grid']:
        for grid_item in grid['items']:
            recurse_item(
                grid_item['item'],
                func,
                nesting=nesting + 1,
                ctx={**ctx, 'grid': grid, 'grid_item': grid_item},
            )
    for stack_slot in item['stack_slots']:
        for inner_item in stack_slot['items']:
            recurse_item(
                inner_item,
                func,
                nesting=nesting + 1,
                ctx={**ctx, 'stack_slot': stack_slot, 'inner_item': inner_item},
            )


def get_total_price(item):
    _my_total_price = 0
    SKIP = ['SecuredContainer', 'Scabbard']
    def tot(item, nesting, ctx):
        nonlocal _my_total_price
        if nesting == 1 and ctx.get('slot', {}).get('id', None) in SKIP:
            return True  # skip
        _my_total_price += int(item['info'].get('price', 0) * item['stack_count'])

    recurse_item(item, tot)
    return _my_total_price


def recurse_delete(item, delete_id):
    if delete_id == item['id']:
        return True  # delete = True

    for slot in item['slots']:
        if recurse_delete(slot['contained_item'], delete_id):
            slot['contained_item'] = []

    for grid in item['grid']:
        new_items = []
        for grid_item in grid['items']:
            if not recurse_delete(grid_item['item'], delete_id):
                new_items.append(grid_item)
        grid['items'] = new_items

    for stack_slot in item['stack_slots']:
        new_items = []

        for inner_item in stack_slot['items']:
            if not recurse_delete(inner_item, delete_id):
                new_items.append(inner_item)
        stack_slot['items'] = new_items


def update_total_price(item):
    pass


def read_item(d: ByteStream, ctx):
    d.store_pos()
    components = []
    slots = []
    grid = []
    stack_slots = []
    out = {
        'id': d.read_string(),
        'template_id': d.read_string(),
        'stack_count': d.read_u32(),
        'is_raid': d.read_bool(),
        'components': components,
        'slots': slots,
        'grid': grid,
        'stack_slots': stack_slots,
    }
    d.store_name(out['id'])

    # print(out)
    out['info'] = get_description(out['template_id'])
    out['name'] = out['info']['name']
    if 'top' in ctx and out['info'] and 'price' in out['info']:
        ctx['top']['total_price'] += int(out['info']['price'] * out['stack_count'])

    num_components = d.read_u32()
    for i in range(num_components):
        components.append(read_polymorph(d, ctx, reraise=True))

    num_slots = d.read_u32()
    for i in range(num_slots):
        slots.append(read_item_descriptor(d, ctx))
    num_grids = d.read_u32()
    for i in range(num_grids):
        grid.append(read_grid(d, ctx))
    num_stack_slots = d.read_u32()
    for i in range(num_stack_slots):
        stack_slots.append(read_stack_slot(d, ctx))
    return out


def json_loot(d: ByteStream, ctx):
    out = {}

    is_top = ctx.get('top', None)
    if not is_top:
        ctx['top'] = out
        out['total_price'] = 0

    if d.read_u8():
        out['id'] = d.read_string()
    out['position'] = d.read_vector()
    out['rotation'] = d.read_vector()
    out['item'] = read_item(d, ctx)
    out['name'] = out['item']['info'].get('name', f'NO NAME/{out["item"]["template_id"]}')
    if d.read_bool():
        p = out['profiles'] = []
        num_profiles = d.read_u32()
        for i in range(num_profiles):
            p.append(d.read_string())

    out['is_static'] = d.read_bool()
    out['use_gravity'] = d.read_bool()
    out['random_rotation'] = d.read_bool()
    out['shift'] = d.read_vector()
    out['platform_id'] = d.read_u16()
    # pprint(out)

    if not is_top:
        ctx.pop('top')

    return out


def resource_key(d: ByteStream, ctx: dict):
    out = {}
    if d.read_bool():
        out['path'] = d.read_string()
    if d.read_bool():
        out['rcid'] = d.read_string()
    return out


def read_repairable(d: ByteStream, ctx: dict):
    return {
        'durability': d.read_f32(),
        'max_durability': d.read_f32(),
    }


def read_fire_mode(d: ByteStream, ctx: dict):
    return {'fire_mode': d.read_u32()}


def read_foldable(d: ByteStream, ctx: dict):
    return {'folded': d.read_bool()}


def read_sight(d: ByteStream, ctx: dict):
    out = {
        'selected_scope': d.read_u32(),
    }
    num_modes = d.read_u32()
    selected_modes = []
    for i in range(num_modes):
        selected_modes.append(d.read_u32())
    num_calibrations = d.read_u32()
    selected_calibrations = []
    for i in range(num_calibrations):
        selected_calibrations.append(d.read_u32())
    return out


def read_food_drink(d: ByteStream, ctx: dict):
    return {'hp': d.read_f32()}


def read_key_usages(d: ByteStream, ctx: dict):
    return {'key_usages': d.read_u32()}


def read_resource_item(d: ByteStream, ctx: dict):
    return {'resource': d.read_f32()}


def read_medkit(d: ByteStream, ctx: dict):
    return {'hp_medkit': d.read_f32()}


def read_quaterion(d: ByteStream, ctx: dict):
    return np.array([d.read_f32(), d.read_f32(), d.read_f32(), d.read_f32()])


def read_transform(d: ByteStream, ctx: dict):
    return {
        'trans_pos': read_vector3(d, ctx),
        'trans_quaterion': read_quaterion(d, ctx),
    }


def read_vector3(d: ByteStream, ctx: dict):
    return np.array([d.read_f32(), d.read_f32(), d.read_f32()])


def read_location_in_grid(d: ByteStream, ctx: dict):
    return {'x': d.read_u32(), 'y': d.read_u32(), 'rot': d.read_u32(), 'is_searched': d.read_bool()}


def read_weighted_loot_spawn(d: ByteStream, ctx: dict):
    return {
        'name': d.read_string(),
        'weight': d.read_f32(),
        'pos': read_vector3(d, ctx),
        'rot': read_vector3(d, ctx),
    }


def read_eft_inv_desc(d: ByteStream, ctx: dict):
    out = {
        'equipment': read_item(d, ctx),
    }
    if d.read_bool():
        out['stash'] = read_item(d, ctx)
    if d.read_bool():
        out['quest_raid_items'] = read_item(d, ctx)
    if d.read_bool():
        out['quest_stash_items'] = read_item(d, ctx)
    out['fast_access'] = read_fast_access(d, ctx)
    return out


def read_fast_access(d: ByteStream, ctx: dict):
    out = {'fast_items': {}}
    num_indexes = d.read_u32()
    for i in range(num_indexes):
        idx = d.read_u32()
        item_id = d.read_string()
        # assert len(item_id) == 0x18
        out['fast_items'][idx] = item_id
    return out


def read_slot_desc(d: ByteStream, ctx: dict):
    return {'id': d.read_string(), 'contained_item': read_item(d, ctx)}


def read_item_in_grid(d: ByteStream, ctx: dict):
    return {
        'location': read_location_in_grid(d, ctx),
        'item': read_item(d, ctx),
    }


def read_light(d: ByteStream, ctx: dict):
    return {'light_active': d.read_bool(), 'mode': d.read_u32()}


def read_lockable(d: ByteStream, ctx: dict):
    return {'locked': d.read_bool()}


def read_map(d: ByteStream, ctx: dict):
    ret = {'markers': []}
    for i in range(d.read_u32()):
        ret['markers'].append(read_logic_map_marker(d, ctx))
    return ret


def read_logic_map_marker(d: ByteStream, ctx: dict):
    return {
        'marker_type': d.read_u32(),
        'x': d.read_u32(),
        'y': d.read_u32(),
        'note': d.read_string(),
    }


def read_toggable(d: ByteStream, ctx: dict):
    return {'is_on': d.read_bool()}


def read_faceshield(d: ByteStream, ctx: dict):
    return {'hits': d.read_u8(), 'hits_seed': d.read_u8()}


def read_dogtag(d: ByteStream, ctx: dict):
    return {
        'nickname': d.read_string(),
        'side': d.read_u32(),
        'level': d.read_u32(),
        'time': d.read_double(),
        'status': d.read_string(),
        'killer': d.read_string(),
        'weapon': d.read_string(),
    }


def read_tag(d: ByteStream, ctx: dict):
    return {'name': d.read_string(), 'color': d.read_u32()}


def json_corpse(d: ByteStream, ctx: dict):
    customizations = {}
    out = {'customizations': customizations}

    num_cus = d.read_u32()

    for i in range(num_cus):
        _id = d.read_u32()
        assert _id < 10, d.debug_rest(8, 4)
        customizations[_id] = d.read_string()

    out['side'] = d.read_u32()
    assert out['side'] < 10, out

    transforms = {}
    bones = d.read_u32()

    for i in range(bones):
        transforms[i] = read_transform(d, ctx)

    if d.read_bool():
        out['id'] = d.read_string()
    out['position'] = read_vector3(d, ctx)
    out['rotation'] = read_vector3(d, ctx)
    out['item'] = read_item(d, ctx)
    if d.read_bool():
        out['profiles'] = []
        for i in range(d.read_u32()):
            out['profiles'].append(d.read_string())
    out['is_static'] = d.read_bool()
    out['use_gravity'] = d.read_bool()
    out['random_rotation'] = d.read_bool()
    out['shift'] = read_vector3(d, ctx)
    out['platform_id'] = d.read_u16()
    return out


def read_move(d: ByteStream, ctx: dict):
    return {
        'id': d.read_string(),
        'from': read_polymorph(d, ctx, reraise=True),
        'to': read_polymorph(d, ctx, reraise=True),
        'move_operation_id': d.read_u16(),
    }

def read_throw(d: ByteStream, ctx: dict):
    return {
        'id': d.read_string(),
        'down_direction': d.read_bool(),
        'throw_operation_id': d.read_u16(),
    }


def read_fold(d: ByteStream, ctx: dict):
    _id = d.read_string()
    print(f'ID: {_id}')
    return {
        'id': _id,
        'value': d.read_bool(),
        'fold_operation_id': d.read_u16(),
    }


def read_magazine(d: ByteStream, ctx: dict):
    return {
        'id': d.read_string(),
        'check_status': d.read_bool(),
        'skill_level': d.read_u32(),
        'check_magazine_operation_id': d.read_u16(),
    }


def read_container(d: ByteStream, ctx: dict):
    return {
        'parent_id': d.read_string(),
        'container_id': d.read_string(),
    }


def read_grid_item_address(d: ByteStream, ctx: dict):
    return {
        'location_in_grid': read_location_in_grid(d, ctx),
        'container': read_container(d, ctx),
    }


def read_bind(d: ByteStream, ctx: dict):
    return {
        'id': d.read_string(),
        'index': d.read_u32(),
        'bind_operation': d.read_u16(),
    }


def read_container(d: ByteStream, ctx: dict):
    return {
        'parent_id': d.read_string(),
        'container_id': d.read_string(),
    }


def read_owner_itself(d: ByteStream, ctx: dict):
    return {
        'owner_container': read_container(d, ctx),
    }


def stub(id, dct=None):
    if dct is None:
        dct= {}
    dct[id] = lambda x, y: {'type': id, 'stub': True}
    return dct

def stubs(ids):
    out = {}
    for id in ids:
        stub(id, out)
    return out

TYPES = {
    **stubs(range(256)),
    0: read_quaterion,
    1: read_transform,
    2: read_vector3,
    4: read_weighted_loot_spawn,
    5: read_eft_inv_desc,
    6: read_fast_access,
    7: read_slot_desc,
    8: read_item_in_grid,
    9: read_grid,
    10: read_stack_slot,
    11: read_item,
    13: read_food_drink,
    14: read_resource_item,
    15: read_light,
    16: read_lockable,
    17: read_map,
    18: read_medkit,
    19: read_repairable,
    20: read_sight,
    21: read_toggable,
    22: read_faceshield,
    23: read_foldable,
    24: read_fire_mode,
    25: read_dogtag,
    26: read_tag,
    27: read_key_usages,
    28: json_loot,
    29: json_corpse,
    34: read_container,
    35: read_grid_item_address,
    36: read_owner_itself,
    41: read_magazine,
    42: read_bind,
    45: read_move,
    51: read_throw,
    53: read_fold,
    999_66: resource_key,
}


def read_many_polymorph(d: ByteStream, ctx={}):
    d.store_pos('many_polymorph')
    num = d.read_u32()
    out = []
    for i in range(num):
        p = read_polymorph(d, ctx)
        if p is not None:
            out.append(p)
        else:
            return out
    return out


def read_polymorph(d: ByteStream, ctx, reraise=False):
    d.store_pos('polymorph', auto=True)
    _type = d.read_u8()

    try:
        # print(f'TYPE: {_type}')
        parser = TYPES[_type]
        if not parser:
            return None
        ret = parser(d, ctx)
        return ret
    except Exception as e:
        if 'many_polymorph' in d.named_positions:
            d.dump_to('json_corpse.bin', 'many_polymorph')
        # print(f'_TYPE: {_type}')
        # log.exception('During parsing')
        # print('exit 79')
        if reraise:
            raise
