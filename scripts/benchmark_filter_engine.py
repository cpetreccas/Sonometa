import argparse
import random
import string
import time


def _rand_word(prefix, min_len=4, max_len=10):
    size = random.randint(min_len, max_len)
    return prefix + "".join(random.choice(string.ascii_lowercase) for _ in range(size))


def build_fake_rows(total_rows):
    albums = [f"Album_{i}" for i in range(120)]
    genres = ["House", "Techno", "Trance", "Breaks", "Minimal", "Deep"]
    publishers = [f"Label_{i}" for i in range(220)]

    rows = []
    for idx in range(total_rows):
        artist = _rand_word("artist_")
        title = _rand_word("title_")
        mixartist = "" if idx % 5 else _rand_word("mix_")
        album = random.choice(albums) if idx % 7 else ""
        genre = random.choice(genres) if idx % 8 else ""
        publisher = random.choice(publishers) if idx % 9 else ""
        year = "" if idx % 6 else str(1990 + (idx % 35))
        cover = "Si" if idx % 4 else "No"
        comment = "" if idx % 3 else "tag1, tag2"
        rows.append((
            f"track_{idx:04d}.mp3",
            artist,
            title,
            mixartist,
            album,
            genre,
            publisher,
            year,
            comment,
            cover,
        ))
    return rows


def filter_rows(rows, criteria):
    columns = ["Filename", "Artist", "Title", "MixArtist", "Album", "Genre", "Publisher", "Year", "Comment", "Cover"]
    col_idx = {name: i for i, name in enumerate(columns)}

    text_filters = criteria.get("text", {})
    combo_filters = criteria.get("combo", {})
    toggles = criteria.get("toggles", {})

    visible = []
    for values in rows:
        ok = True

        for col_name, search_val in text_filters.items():
            idx = col_idx[col_name]
            cell_val = str(values[idx]).lower()
            if search_val not in cell_val:
                ok = False
                break

        if not ok:
            continue

        for col_name, selected_val in combo_filters.items():
            idx = col_idx[col_name]
            cell_val = str(values[idx]).strip()
            if selected_val == "[ Vacio ]":
                if cell_val != "":
                    ok = False
                    break
            elif cell_val != selected_val:
                ok = False
                break

        if not ok:
            continue

        if toggles.get("no_year"):
            year_val = str(values[col_idx["Year"]]).strip()
            if year_val not in ("", "0", "None"):
                ok = False

        if ok and toggles.get("no_cover"):
            cover_val = str(values[col_idx["Cover"]]).strip().lower()
            if cover_val in ("si", "yes", "true", "1"):
                ok = False

        if ok and toggles.get("no_comment"):
            comment_val = str(values[col_idx["Comment"]]).strip()
            if comment_val != "":
                ok = False

        if ok:
            visible.append(values)

    return visible


def run_benchmark(rows, iterations):
    criteria_sets = [
        {
            "text": {"Artist": "artist_a", "Title": "title_"},
            "combo": {},
            "toggles": {"no_year": False, "no_cover": False, "no_comment": False},
        },
        {
            "text": {},
            "combo": {"Genre": "House"},
            "toggles": {"no_year": False, "no_cover": True, "no_comment": False},
        },
        {
            "text": {"Title": "z"},
            "combo": {"Album": "[ Vacio ]"},
            "toggles": {"no_year": True, "no_cover": False, "no_comment": True},
        },
    ]

    started = time.perf_counter()
    total_visible = 0

    for i in range(iterations):
        criteria = criteria_sets[i % len(criteria_sets)]
        visible = filter_rows(rows, criteria)
        total_visible += len(visible)

    elapsed = time.perf_counter() - started
    avg_ms = (elapsed / iterations) * 1000.0

    print(f"rows={len(rows)} iterations={iterations}")
    print(f"total_seconds={elapsed:.4f}")
    print(f"avg_ms_per_filter={avg_ms:.3f}")
    print(f"total_visible_acc={total_visible}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark simple del motor de filtro sobre 4,000 filas.")
    parser.add_argument("--rows", type=int, default=4000, help="Cantidad de filas sinteticas.")
    parser.add_argument("--iterations", type=int, default=120, help="Cantidad de iteraciones de filtrado.")
    parser.add_argument("--seed", type=int, default=42, help="Semilla para datos reproducibles.")
    args = parser.parse_args()

    random.seed(args.seed)
    data_rows = build_fake_rows(args.rows)
    run_benchmark(data_rows, args.iterations)

