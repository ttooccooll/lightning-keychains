#!/usr/bin/env python3
"""catalog.py - picture sheet of back designs (for your shop page / meetup table).

    python catalog.py                       # the curated set -> out/catalog.png
    python catalog.py coffee barber trumpet # just these
"""
import math
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import lnkey

GROUPS = [
    ("Food, drink & tips", "classic", ["coffee", "barista", "bartender", "beer", "wine", "server", "chef", "pizza",
                                       "taco", "burger", "icecream", "bakery", "foodtruck", "bbq"]),
    ("Trades & services", "ocean", ["barber", "salon", "mechanic", "handyman", "carwash", "driver",
                                    "delivery", "cleaning", "lawn", "plumber", "electrician", "photo", "dogwalker",
                                    "pets", "babysitter", "tutor", "fitness", "florist", "printing", "realtor"]),
    ("Makers, farm & market", "forest", ["eggs", "farm", "tractor", "honey", "produce", "corn", "market", "thrift",
                                         "books", "art", "candle"]),
    ("Music & arts", "ohio", ["music", "guitar", "electric", "trumpet", "trombone", "sax", "piano", "violin", "mic",
                              "dj", "vinyl", "theater"]),
    ("Interests", "sunny", ["heart", "star", "smile", "peace", "cross", "church", "chess", "hiking", "tent", "tree",
                            "mountain", "fishing", "surf", "gaming", "dice", "rocket", "football", "baseball",
                            "basketball", "soccer", "golf", "bowling", "skate", "anchor"]),
    ("Bitcoin", "bitcoin", ["btc", "bolt", "sats", "pill", "zap", "tipjar", "miner", "tips", "piggy", "giving", "key", "shield", "pickaxe", "node", "wallet"]),
]


def sheet(groups, path, cols=8, address="you@wallet.com"):
    import os
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    rows = sum(math.ceil(len(g[2]) / cols) for g in groups)
    cell = 1.55
    fig = plt.figure(figsize=(cols * cell, rows * cell * 1.16 + len(groups) * 0.42 + 0.9), dpi=170)
    fig.patch.set_facecolor("#E9E6DF")
    H = fig.get_figheight()
    y = H - 0.75
    fig.text(0.5, 1 - 0.32 / H, "Back-side designs", ha="center", va="center", fontsize=17, weight="bold",
             color="#222")
    fig.text(0.5, 1 - 0.58 / H, "Pick a picture or send a logo. Any colourway.",
             ha="center", va="center", fontsize=8.5, color="#555")
    for title, colorway, names in groups:
        y -= 0.34
        fig.text(0.02, y / H, title, fontsize=10.5, weight="bold", color="#333", va="center")
        y -= 0.08
        for i, name in enumerate(names):
            r, c = divmod(i, cols)
            tag = lnkey.Tag(lnkey.spec_from(address, "retail", back=name, colorway=colorway, back_bottom=""))
            ax = fig.add_axes([c / cols + 0.004, (y - (r + 1) * cell * 1.16) / H, 1 / cols - 0.008,
                               cell * 1.16 / H])
            lnkey.draw_face(ax, tag, "back")
            ax.set_xlim(-tag.R - 3, tag.R + 3)
            ax.set_ylim(-tag.R - 9, tag.height - tag.R + 2)
            ax.set_aspect("equal")
            ax.axis("off")
            ax.text(0, -tag.R - 5.5, name, ha="center", va="center", fontsize=7.5, color="#333")
            for n in tag.notes:
                print(f"{name}: {n}")
        y -= math.ceil(len(names) / cols) * cell * 1.16
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    print("wrote", path)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sheet([("Selected", "classic", sys.argv[1:])], "out/catalog_selected.png")
    else:
        sheet(GROUPS, "out/catalog.png")
