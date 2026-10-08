"""AirPack4 schedule clocks and Particle+ automatic filter-check time."""

from .airpack4 import airpack4_entities, is_airpack4
from .const import DOMAIN
from .particle import is_particle, particle_entities


async def async_setup_entry(hass, entry, async_add_entities):
    if is_airpack4(entry):
        async_add_entities(airpack4_entities("time", hass.data[DOMAIN][entry.entry_id]["coordinator"], entry))
    elif is_particle(entry):
        async_add_entities(particle_entities("time", hass.data[DOMAIN][entry.entry_id]["coordinator"], entry))
