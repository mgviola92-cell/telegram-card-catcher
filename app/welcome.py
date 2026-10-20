"""Reusable Telegram welcome screen and currently working command menu."""
from telebot import types

BOT_USERNAME = "Card_Kout_bot"

WELCOME_TEXT = (
    "👋 𝗛𝗘𝗬 𝗧𝗛𝗘𝗥𝗘!\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "🃏 𝗖𝗔𝗥𝗗 𝗞𝗢𝗨𝗧 — 𝗖𝗛𝗔𝗥𝗔𝗖𝗧𝗘𝗥 𝗖𝗔𝗧𝗖𝗛𝗘𝗥\n\n"
    "🌸 Anime • Manga • Manhwa • Webtoon\n"
    "⚔️ Waifu • Husbando • Game Characters\n\n"
    "✨ Group မှာ စကားပြောတဲ့ Message အရေအတွက် ပြည့်ရင် "
    "Random Character ပေါ်လာမယ်။\n"
    "🎯 Character နာမည်ကို Chat ထဲမှာ မှန်အောင်အရင်ရိုက်တဲ့သူက Catch ရမယ်။\n"
    "🌍 Group အားလုံးမှာ Collection တစ်ခုတည်းကို သုံးနိုင်တယ်။\n\n"
    "👇 အောက်က Buttons တွေကနေ စတင်နိုင်ပါတယ်။"
)

COMMANDS_TEXT = (
    "📚 𝗖𝗔𝗥𝗗 𝗞𝗢𝗨𝗧 — 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "🃏 𝗖𝗢𝗟𝗟𝗘𝗖𝗧𝗜𝗢𝗡\n"
    "/harem — Global Collection ကြည့်ရန်\n"
    "/collection — Collection ကြည့်ရန်\n"
    "/recent — Recent Cards ကြည့်ရန်\n"
    "/check ID — Card အချက်အလက်ကြည့်ရန်\n"
    "/view ID — Card အချက်အလက်ကြည့်ရန်\n\n"
    "⭐ 𝗙𝗔𝗩𝗢𝗥𝗜𝗧𝗘𝗦\n"
    "/fav ID — Favorite ထည့်ရန်\n"
    "/mfav ID1 ID2 — အများကြီး Favorite ထည့်ရန်\n"
    "/unfav ID — Favorite ဖယ်ရန်\n\n"
    "🎁 𝗚𝗜𝗙𝗧 & 𝗧𝗥𝗔𝗗𝗘\n"
    "/gift MY_ID — Member ကို Reply ပြီး Gift ပေးရန်\n"
    "/trade MY_ID THEIR_ID — Reply ပြီး Trade တောင်းရန်\n"
    "⏳ Receiver က 10 မိနစ်အတွင်း Accept/Decline လုပ်နိုင်တယ်။\n\n"
    "🏆 𝗟𝗘𝗔𝗗𝗘𝗥𝗕𝗢𝗔𝗥𝗗\n"
    "/top — Global top catchers\n"
    "/gtop — Group top catchers\n"
    "/today — Today's catches (Myanmar time)\n\n"
    "🔎 𝗦𝗘𝗔𝗥𝗖𝗛\n"
    "/search NAME — Character/Series ရှာရန်\n\n"
    "⚙️ 𝗚𝗥𝗢𝗨𝗣 𝗔𝗗𝗠𝗜𝗡\n"
    "/changetime COUNT — Spawn Message Count ပြင်ရန် (10–500)\n\n"
    "📌 Spawn ပုံပေါ်လာရင် Character နာမည်ကို Chat ထဲမှာ ရိုက်ပါ။\n"
    "🚧 Market နဲ့ Advanced Cards ကို ဆက်တည်ဆောက်နေပါတယ်။"
)


def welcome_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(
        "➕ 𝗔𝗗𝗗 𝗠𝗘 𝗧𝗢 𝗬𝗢𝗨𝗥 𝗚𝗥𝗢𝗨𝗣 ➕",
        url=f"https://t.me/{BOT_USERNAME}?startgroup=true",
    ))
    kb.row(
        types.InlineKeyboardButton("🃏 𝗠𝗬 𝗛𝗔𝗥𝗘𝗠", callback_data="ui:harem"),
        types.InlineKeyboardButton("📚 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦", callback_data="ui:cmds"),
    )
    kb.add(types.InlineKeyboardButton("❓ 𝗛𝗢𝗪 𝗧𝗢 𝗣𝗟𝗔𝗬", callback_data="ui:guide"))
    return kb


def return_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🏠 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", callback_data="ui:home"))
    return kb


GUIDE_TEXT = (
    "🎮 𝗛𝗢𝗪 𝗧𝗢 𝗣𝗟𝗔𝗬\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "① Bot ကို Group ထဲထည့်ပါ။\n"
    "② BotFather မှာ Group Privacy ကို Disable လုပ်ထားရမယ်။\n"
    "③ Group Message Count ပြည့်ရင် Character ပုံပေါ်လာမယ်။\n"
    "④ Character ရဲ့နာမည်ကို ပထမဆုံးမှန်အောင် ရိုက်ပါ။\n"
    "⑤ ရထားတဲ့ Card ကို /harem နဲ့ ကြည့်ပါ။\n\n"
    "💡 Admin တွေက /changetime 35 နဲ့ Spawn Rate ပြင်နိုင်ပါတယ်။"
)
