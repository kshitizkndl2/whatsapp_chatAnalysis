import re
import math
import unicodedata
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from urlextract import URLExtract
from wordcloud import WordCloud
import nltk
nltk.download('stopwords')
from nltk.corpus import stopwords
from collections import Counter

import regex

extract = URLExtract()

_WHATSAPP_TAIL_TAGS = re.compile(
    r"(?:\s*<This message was edited>|\s*<This message was deleted>)+$",
    re.IGNORECASE,
)


_TOP_RANKED_ITEMS = 50


def _figure_ranked_horizontal(
    labels: list[str],
    values: list[int],
    title: str,
    xlabel: str,
    *,
    bar_color: str = "steelblue",
):
    """Horizontal bar chart for many ranked items (readable layout for ~50 rows)."""
    n = len(labels)
    fig_h = min(26, max(5.5, n * 0.33))
    fig_w = 11
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    y_pos = list(range(n))
    ax.barh(y_pos, values, align="center", color=bar_color, height=0.72)
    ax.set_yticks(y_pos, labels=labels)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_title(title, fontsize=14, pad=10)
    y_font = max(9, min(12, 450 // max(n, 12)))
    ax.tick_params(axis="y", labelsize=y_font)
    ax.tick_params(axis="x", labelsize=10)
    ax.margins(x=0.06)
    fig.tight_layout()
    return fig


def _strip_whatsapp_message_suffixes(text) -> str:
    """Remove trailing WhatsApp export tags (e.g. ``<This message was edited>``)."""
    if pd.isna(text):
        return ""
    s = str(text).strip()
    while True:
        prev = s
        s = _WHATSAPP_TAIL_TAGS.sub("", s).rstrip()
        if s == prev:
            break
    return s


def _extract_emojis_from_string(s: str) -> list[str]:
    """Grapheme-aware emoji extraction (no third-party ``emoji`` package)."""
    if not s:
        return []
    found: list[str] = []
    for cluster in regex.findall(r"\X", s, regex.V1):
        if regex.search(r"\p{Extended_Pictographic}", cluster):
            found.append(cluster)
    return found


def _emoji_caption_name(glyph: str, max_chars: int = 36) -> str:
    """Short Unicode-based description for chart labels (not CLDR short names)."""
    parts: list[str] = []
    for ch in glyph:
        try:
            nm = unicodedata.name(ch)
        except ValueError:
            continue
        if "ZERO WIDTH" in nm or "VARIATION SELECTOR" in nm:
            continue
        parts.append(nm.replace("_", " ").title())
    if not parts:
        return "Emoji"
    s = " · ".join(parts)
    if len(s) > max_chars:
        return s[: max_chars - 1] + "…"
    return s


def _wedge_label_fontsize(width_deg: float, n_chars: int) -> int:
    """Font size for a name that must stay inside one wedge (wider slice → larger type)."""
    w = max(float(width_deg), 2.0)
    base = 12.0 + (w / 360.0) * 100.0
    fs = int(base / max(0.85, (max(n_chars, 6) ** 0.35) * 0.5))
    return max(11, min(22, fs))


def _wedge_unicode_caption(glyph: str, width_deg: float) -> str:
    """Caption length scales with angular width so narrow slices get shorter strings."""
    max_chars = max(14, min(52, int(10 + width_deg * 0.52)))
    return _emoji_caption_name(glyph, max_chars=max_chars)


def _word_count_excluding_links(message, links_longest_first):
    if pd.isna(message):
        return 0
    s = str(message)
    for url in links_longest_first:
        if url in s:
            s = s.replace(url, " ")
    return len(s.split())


def fetch_stats(name, df):
    df = df.copy()
    df["Message"] = df["Message"].apply(_strip_whatsapp_message_suffixes)

    if name != "Overall":
        system_pattern = re.compile(
    r"""
    (missed\s+)?(video|voice)\s+call.*
    | video\s+omitted
    | image\s+omitted
    | audio\s+omitted
    | gif\s+omitted
    | sticker\s+omitted
    | media\s+omitted

    | \S+\.(pdf|docx?|pptx?|xlsx?|jpg|png|jpeg)\s*[•·●]\s*\d+\s+pages?\s+document\s+omitted
    | \S+\s+document\s+omitted

    | waiting\s+for\s+this\s+message.*


    | answered\s+on\s+other\s+device
    | no\s+answer

    | .*added\s+you
    | .*created(\s+this)?\s+group
    | .*joined.*
    | .*left.*
    | .*removed.*

    | .*end-to-end\s+encrypted.*   # 🔥 FIXED (loose match)

    """,
    re.IGNORECASE | re.VERBOSE
)

        df_cleaned = df[df['Name'] == name]
        df_cleaned = df_cleaned[~df_cleaned["Message"].str.contains(system_pattern, na=False)].reset_index(drop=True)
        lst = []
        cleaned_names = df[df['Name'] == name]['Name']
        cleaned_names = [name for name in cleaned_names if ',' not in str(name)]
        total_messages = len(cleaned_names)
        links = []
        for message in df_cleaned['Message']:
            links.extend(extract.find_urls(message))
        link_count = len(links)
        links_for_strip = sorted(set(links), key=len, reverse=True)
        media_pattern = r"(video|image|audio|gif|sticker|document|media) omitted"
        media_count = df[df['Name'] == name]["Message"].str.contains(media_pattern, case=False, regex=True).sum()
        total_words = int(
            df_cleaned["Message"]
            .apply(lambda m: _word_count_excluding_links(m, links_for_strip))
            .sum()
        )
        
        lst.append(total_messages)
        lst.append(total_words)
        lst.append(media_count)
        lst.append(link_count)

        return lst, df_cleaned,links
    else:
        lst = []
        system_pattern = re.compile(
    r"""
    (missed\s+)?(video|voice)\s+call.*
    | video\s+omitted
    | image\s+omitted
    | audio\s+omitted
    | gif\s+omitted
    | sticker\s+omitted
    | media\s+omitted

    | \S+\.(pdf|docx?|pptx?|xlsx?|jpg|png|jpeg)\s*[•·●]\s*\d+\s+pages?\s+document\s+omitted
    | \S+\s+document\s+omitted

    | waiting\s+for\s+this\s+message.*


    | answered\s+on\s+other\s+device
    | no\s+answer

    | .*added\s+you
    | .*created(\s+this)?\s+group
    | .*joined.*
    | .*left.*
    | .*removed.*

    | .*end-to-end\s+encrypted.*   # 🔥 FIXED (loose match)

    """,
    re.IGNORECASE | re.VERBOSE
)

    df_cleaned = df[~df["Message"].str.contains(system_pattern, na=False)].reset_index(drop=True)
    cleaned_names = df['Name']
    cleaned_names = [name for name in cleaned_names if ',' not in str(name)]
            
    total_messages = len(cleaned_names)
    links = []
    for message in df['Message']:
            links.extend(extract.find_urls(message))
    link_count = len(links)
    links_for_strip = sorted(set(links), key=len, reverse=True)
    total_words = int(
        df_cleaned["Message"]
        .apply(lambda m: _word_count_excluding_links(m, links_for_strip))
        .sum()
    )
    media_pattern = r"(video|image|audio|gif|sticker|document|media) omitted"

    media_count = df["Message"].str.contains(media_pattern, case=False, regex=True).sum()
    

        
    lst.append(total_messages)
    lst.append(total_words)
    lst.append(media_count)
    lst.append(link_count)
      
    return lst,df_cleaned,links

def fetch_wordcloud(wordcloud_df, links):
    st.title("Word Cloud of Links Shared")
    if links:
        words = " ".join(" ".join(links).split(','))
        wc = WordCloud(width=800, height=800, background_color='black').generate(words)
        st.image(wc.to_array())
    else:
        st.write("No links shared")
    st.title("Word Cloud of Words Shared")
    if len(wordcloud_df['Message'].values) > 0:
        stop_words = stopwords.words('english')
        words = wordcloud_df['Message'].values
        words = [word for word in words if not any(link in str(word) for link in links)]
        words = [word for word in words if word not in stop_words]
        if len(words) > 0:
            words = " ".join(" ".join(words).split('],['))
            wc = WordCloud(width=800, height=800, background_color='black').generate(words)
            st.image(wc.to_array())
        else:
            st.write("No words shared")
    else:
        st.write("No words shared")
def fetch_most_busy_users(df):
    st.title("Most Busy Users")
    df = df.copy()
    df = df[~df["Name"].astype(str).str.contains(",", na=False)]
    counts = df["Name"].value_counts().head(5)
    total = len(df)
    if total == 0 or counts.empty:
        st.write("No messages to plot.")
        return

    names = counts.index.tolist()
    vals = counts.values
    n = len(names)
    fig, ax = plt.subplots(figsize=(10, max(4.0, n * 0.65)))
    y_pos = range(n)
    bars = ax.barh(y_pos, vals, color="steelblue")
    ax.set_yticks(y_pos, labels=names)
    ax.invert_yaxis()
    ax.set_xlabel("Messages sent")
    ax.set_ylabel("User")
    ax.set_title("Most busy users — % of all messages in this chat")
    ax.margins(x=0.18)
    pct_labels = [f"{100 * v / total:.1f}%" for v in vals]
    ax.bar_label(bars, labels=pct_labels, padding=4, fontsize=10)
    fig.tight_layout()
    st.pyplot(fig, clear_figure=True)
    plt.close(fig)
def most_common_words(df,links):
    st.title("Most Common Words")
    stop_words = stopwords.words('english')
    words = df['Message'].values
    words = [word for word in words if not any(link in str(word) for link in links)]
    unique_words = list(set(words))
    if len(unique_words) > 0:
        words = " ".join(" ".join(words).split('],['))
        words = words.split()
        word_counts = Counter(words)
        ranked = word_counts.most_common(_TOP_RANKED_ITEMS)
        labels = [w for w, _ in ranked]
        values = [c for _, c in ranked]
        fig = _figure_ranked_horizontal(
            labels,
            values,
            f"Most common words (top {len(ranked)})",
            "Count",
        )
        st.pyplot(fig, clear_figure=True, use_container_width=True)
        plt.close(fig)
    else:
        st.write("No words to plot.")
def fetch_emojis(df):
    st.title("Most Common Emojis")
    all_emojis = []
    for message in df["Message"].astype(str):
        all_emojis.extend(_extract_emojis_from_string(message))
    if not all_emojis:
        st.write("No emojis found.")
        return
    ranked = Counter(all_emojis).most_common(_TOP_RANKED_ITEMS)
    glyphs = [e for e, _ in ranked]
    counts = [c for _, c in ranked]
    if not counts:
        st.write("No emojis found.")
        return

    n = len(glyphs)
    emoji_fs = max(20, min(38, 1300 // max(n, 8)))

    fig, ax = plt.subplots(figsize=(15, 15))
    colors = [plt.cm.tab20(i % 20) for i in range(n)]
    wedges, texts, autotexts = ax.pie(
        counts,
        labels=None,
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
        colors=colors,
        pctdistance=0.82,
        textprops={"fontsize": 11},
        wedgeprops={"linewidth": 0.5, "edgecolor": "white"},
    )
    plt.setp(autotexts, fontsize=15, weight="bold", color="#141414", zorder=6)
    if texts:
        plt.setp(texts, visible=False)

    for w, g in zip(wedges, glyphs):
        dtheta_deg = abs(w.theta2 - w.theta1)
        mid_deg = (w.theta1 + w.theta2) / 2.0
        ang = math.radians(mid_deg)
        caption = _wedge_unicode_caption(g, dtheta_deg)
        name_fs = _wedge_label_fontsize(dtheta_deg, len(caption))

        r_emoji = 0.34
        r_name = 0.58
        emoji_t = ax.text(
            r_emoji * math.cos(ang),
            r_emoji * math.sin(ang),
            g,
            ha="center",
            va="center",
            fontsize=emoji_fs,
            clip_path=w,
            clip_on=True,
            zorder=4,
        )
        name_t = ax.text(
            r_name * math.cos(ang),
            r_name * math.sin(ang),
            caption,
            ha="center",
            va="center",
            rotation=mid_deg - 90,
            rotation_mode="anchor",
            fontsize=name_fs,
            color="#121212",
            clip_path=w,
            clip_on=True,
            zorder=5,
        )
        # Some matplotlib builds need the patch explicitly for clipping text.
        emoji_t.set_clip_path(w)
        name_t.set_clip_path(w)

    ax.set_title(
        f"Most common emojis — top {n} (max {_TOP_RANKED_ITEMS})",
        fontsize=15,
        pad=18,
    )
    ax.axis("equal")
    fig.tight_layout()
    st.pyplot(fig, clear_figure=True, use_container_width=True)
    plt.close(fig)




