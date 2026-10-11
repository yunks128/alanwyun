"""Entry point for the web build (pygbag looks for main.py). Desktop: run this or alien_boom_boom.py."""
import asyncio

import pygame  # noqa: F401  (tells pygbag to bundle pygame)

from alien_boom_boom import main

asyncio.run(main())
