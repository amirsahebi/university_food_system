#!/usr/bin/env python3
"""
Apply branded food images to Javan Foods catalog.
Matches foods by Name first, then by ID (for production 74 items), then by keywords.
"""
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, '/app')
sys.path.insert(0, '/opt/javanfoods/backend/app')
sys.path.insert(0, '/opt/javanfoods/backend')

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'university_food_system.settings')
django.setup()

from food.models import Food

# Production Exact Name Mapping
NAME_MAPPING = {
    # Iranian Dishes
    'چلو کباب مرغ': 'clean_dish_cartoon_branded.jpg',
    'چلو کباب گوسفندی': 'clean_dish_cartoon_branded.jpg',
    'چلو جوجه': 'branded_joojeh_kabab.jpg',
    'چلو جوجه کباب': 'branded_joojeh_kabab.jpg',
    'زرشک پلو با مرغ': 'branded_zereshk_polo.jpg',
    'چلو خورشت فسنجان': 'branded_fesenjan.jpg',
    'ماکارونی گیاهی': 'branded_macaroni.jpg',
    'ماکارانی با گوشت': 'branded_macaroni.jpg',
    'ماکارونی': 'branded_macaroni.jpg',
    'استانبولی با مرغ': 'branded_lubia_polo.jpg',
    'رشته پلو': 'branded_adas_polo.jpg',
    'باقالی پلو با مرغ': 'branded_baghali_polo.jpg',
    'باقالی پلو با گوشت': 'branded_baghali_polo.jpg',
    'شوید پلو با تن ماهی': 'branded_chelo_mahi.jpg',
    'عدس پلو': 'branded_adas_polo.jpg',
    'چلو خورشت قورمه سبزی': 'branded_ghormeh_sabzi.jpg',
    'قورمه سبزی': 'branded_ghormeh_sabzi.jpg',
    'قرمه سبزی': 'branded_ghormeh_sabzi.jpg',
    'چلوخورشت قیمه': 'branded_gheymeh.jpg',
    'خورشت قیمه سیب‌زمینی': 'branded_gheymeh.jpg',
    'قیمه': 'branded_gheymeh.jpg',
    'کوکو سیب زمینی': 'branded_kashk_bademjan.jpg',
    'کتلت گوشت': 'branded_burger_beef.jpg',
    'کوکو سبزی': 'branded_kashk_bademjan.jpg',
    'لوبیا پلو': 'branded_lubia_polo.jpg',
    'شیرین پلو': 'branded_zereshk_polo.jpg',
    'آبگوشت دیزی': 'branded_abgoosht.jpg',
    'کشک بادمجان': 'branded_kashk_bademjan.jpg',
    'نیم پرس کباب مرغ': 'clean_dish_cartoon_branded.jpg',
    'نیم پرس جوجه': 'branded_joojeh_kabab.jpg',
    'نیم پرس کباب گوسفندی': 'clean_dish_cartoon_branded.jpg',
    'کتلت مرغ': 'branded_sandwich_morgh.jpg',
    'چلو ماهی': 'branded_chelo_mahi.jpg',
    'خوراک کت وبال 8 تکه ای': 'branded_fileh_sookhari.jpg',
    'خوراک کت وبال 6تکه': 'branded_fileh_sookhari.jpg',
    'نیم پرس چلو مرغ': 'branded_zereshk_polo.jpg',
    'کره کباب جوجه': 'branded_joojeh_kabab.jpg',
    'کره کباب مرغ': 'clean_dish_cartoon_branded.jpg',
    'کره کباب گوسفندی': 'clean_dish_cartoon_branded.jpg',

    # Pizzas
    'پیتزا مخلوط تک نفره': 'branded_pizza_makhloot.jpg',
    'پیتزا مخلوط دونفره': 'branded_pizza_makhloot.jpg',
    'پیتزا مخلوط ایتالیایی': 'branded_pizza_makhloot.jpg',
    'پیتزا مرغ تک نفره': 'branded_pizza_chicken_mushroom.jpg',
    'پیتزا مرغ دو نفره': 'branded_pizza_chicken_mushroom.jpg',
    'پیتزا مرغ ایتالیایی': 'branded_pizza_chicken_mushroom.jpg',
    'پیتزا سبزیجات تک نفره': 'branded_pizza_sabzijat.jpg',
    'پیتزا سبزیجات دونفره': 'branded_pizza_sabzijat.jpg',
    'پیتزا سبزیجات ایتالیایی': 'branded_pizza_sabzijat.jpg',
    'پیتزا پپرونی تک نفره': 'branded_pizza_pepperoni.jpg',
    'پیتزا پپرونی دونفره': 'branded_pizza_pepperoni.jpg',
    'پیتزا پپرونی ایتالیایی': 'branded_pizza_pepperoni.jpg',
    'پیتزا مخصوص تک نفره': 'branded_pizza_makhsoos.jpg',
    'پیتزا مخصوص دونفره': 'branded_pizza_makhsoos.jpg',
    'پیتزا مخصوص ایتالیایی': 'branded_pizza_makhsoos.jpg',
    'پیتزا گوشت و قارچ 2نفره': 'branded_pizza_makhsoos.jpg',
    'پیتزا گوشت وقارچ ایتالیایی': 'branded_pizza_makhsoos.jpg',

    # Sandwiches & Burgers
    'بندری': 'branded_sosis_bandari.jpg',
    'کوکتل': 'branded_hotdog_paniri.jpg',
    'کوکتل بلغاری': 'branded_hotdog_paniri.jpg',
    'فلافل': 'branded_felafel.jpg',
    'همبرگر 60%': 'branded_burger_beef.jpg',
    'همبرگر ویژه': 'branded_burger_beef.jpg',
    'همبرگر دست ساز 95%': 'branded_burger_beef.jpg',
    'هات داگ': 'branded_hotdog_paniri.jpg',
    'هات داگ پنیری': 'branded_hotdog_paniri.jpg',
    'ساندویچ مرغ': 'branded_sandwich_morgh.jpg',
    'ساندویچ کالباس خشک': 'branded_zhambon_tanoori.jpg',
    'ساندویچ کالباس لیونر': 'branded_zhambon_tanoori.jpg',
    'ساندویچ ژامبون گوشت 90%': 'branded_zhambon_tanoori.jpg',
    'ساندویچ ژامبون مرغ 90%': 'branded_zhambon_tanoori.jpg',

    # Fried & Sides
    'سبد سوخاری': 'branded_fileh_sookhari.jpg',
    'فیله سوخاری': 'branded_fileh_sookhari.jpg',
    'قارچ سوخاری': 'branded_gharch_sookhari.jpg',
    'سیب سوخاری': 'branded_sib_belgiki.jpg',
    'سیب زمینی بلژیکی': 'branded_sib_belgiki.jpg',
    'توپک تنوری': 'branded_gharch_sookhari.jpg',
    'کراکت': 'branded_fileh_sookhari.jpg',
    'کردنبلو': 'branded_fileh_sookhari.jpg',
}

# Production ID Fallback (for items 1-74)
ID_MAPPING = {
    1: 'clean_dish_cartoon_branded.jpg',
    2: 'clean_dish_cartoon_branded.jpg',
    3: 'branded_joojeh_kabab.jpg',
    4: 'branded_zereshk_polo.jpg',
    5: 'branded_fesenjan.jpg',
    6: 'branded_macaroni.jpg',
    7: 'branded_macaroni.jpg',
    8: 'branded_lubia_polo.jpg',
    9: 'branded_adas_polo.jpg',
    10: 'branded_baghali_polo.jpg',
    11: 'branded_chelo_mahi.jpg',
    12: 'branded_adas_polo.jpg',
    13: 'branded_ghormeh_sabzi.jpg',
    14: 'branded_gheymeh.jpg',
    15: 'branded_kashk_bademjan.jpg',
    16: 'branded_burger_beef.jpg',
    17: 'branded_kashk_bademjan.jpg',
    18: 'branded_pizza_makhloot.jpg',
    19: 'branded_pizza_chicken_mushroom.jpg',
    20: 'branded_pizza_sabzijat.jpg',
    21: 'branded_pizza_pepperoni.jpg',
    22: 'branded_pizza_makhsoos.jpg',
    23: 'branded_pizza_makhsoos.jpg',
    24: 'branded_pizza_makhloot.jpg',
    25: 'branded_pizza_chicken_mushroom.jpg',
    26: 'branded_pizza_sabzijat.jpg',
    27: 'branded_pizza_pepperoni.jpg',
    28: 'branded_pizza_makhsoos.jpg',
    29: 'branded_pizza_makhsoos.jpg',
    30: 'branded_pizza_makhloot.jpg',
    31: 'branded_pizza_pepperoni.jpg',
    32: 'branded_pizza_sabzijat.jpg',
    33: 'branded_pizza_chicken_mushroom.jpg',
    34: 'branded_pizza_makhsoos.jpg',
    35: 'branded_sosis_bandari.jpg',
    36: 'branded_hotdog_paniri.jpg',
    37: 'branded_felafel.jpg',
    38: 'branded_burger_beef.jpg',
    39: 'branded_burger_beef.jpg',
    40: 'branded_burger_beef.jpg',
    41: 'branded_hotdog_paniri.jpg',
    42: 'branded_hotdog_paniri.jpg',
    43: 'branded_lubia_polo.jpg',
    44: 'branded_macaroni.jpg',
    45: 'branded_zereshk_polo.jpg',
    46: 'branded_fileh_sookhari.jpg',
    47: 'branded_fileh_sookhari.jpg',
    48: 'branded_gharch_sookhari.jpg',
    50: 'branded_abgoosht.jpg',
    51: 'branded_kashk_bademjan.jpg',
    52: 'clean_dish_cartoon_branded.jpg',
    53: 'branded_joojeh_kabab.jpg',
    54: 'clean_dish_cartoon_branded.jpg',
    55: 'branded_sandwich_morgh.jpg',
    56: 'branded_sandwich_morgh.jpg',
    57: 'branded_chelo_mahi.jpg',
    58: 'branded_fileh_sookhari.jpg',
    59: 'branded_zereshk_polo.jpg',
    60: 'branded_sib_belgiki.jpg',
    61: 'branded_sib_belgiki.jpg',
    62: 'branded_gharch_sookhari.jpg',
    63: 'branded_fileh_sookhari.jpg',
    64: 'branded_fileh_sookhari.jpg',
    65: 'branded_joojeh_kabab.jpg',
    66: 'clean_dish_cartoon_branded.jpg',
    67: 'clean_dish_cartoon_branded.jpg',
    68: 'branded_fileh_sookhari.jpg',
    69: 'branded_hotdog_paniri.jpg',
    70: 'branded_sandwich_morgh.jpg',
    71: 'branded_zhambon_tanoori.jpg',
    72: 'branded_zhambon_tanoori.jpg',
    73: 'branded_zhambon_tanoori.jpg',
    74: 'branded_zhambon_tanoori.jpg',
}

# Fuzzy Keyword Fallback
KEYWORD_MAPPING = [
    (['کباب', 'کوبیده'], 'clean_dish_cartoon_branded.jpg'),
    (['جوجه'], 'branded_joojeh_kabab.jpg'),
    (['زرشک'], 'branded_zereshk_polo.jpg'),
    (['فسنجان'], 'branded_fesenjan.jpg'),
    (['قورمه', 'قرمه'], 'branded_ghormeh_sabzi.jpg'),
    (['قیمه'], 'branded_gheymeh.jpg'),
    (['ماکارونی', 'ماکارانی'], 'branded_macaroni.jpg'),
    (['لوبیا', 'استانبولی'], 'branded_lubia_polo.jpg'),
    (['عدس', 'رشته پلو'], 'branded_adas_polo.jpg'),
    (['باقالی'], 'branded_baghali_polo.jpg'),
    (['ماهی'], 'branded_chelo_mahi.jpg'),
    (['دیزی', 'آبگوشت'], 'branded_abgoosht.jpg'),
    (['کشک', 'کوکو'], 'branded_kashk_bademjan.jpg'),
    (['پپرونی'], 'branded_pizza_pepperoni.jpg'),
    (['مخلوط'], 'branded_pizza_makhloot.jpg'),
    (['سبزیجات'], 'branded_pizza_sabzijat.jpg'),
    (['پیتزا', 'مرغ'], 'branded_pizza_chicken_mushroom.jpg'),
    (['پیتزا'], 'branded_pizza_makhsoos.jpg'),
    (['برگر', 'همبرگر'], 'branded_burger_beef.jpg'),
    (['هات داگ', 'کوکتل', 'سوسیس'], 'branded_hotdog_paniri.jpg'),
    (['بندری'], 'branded_sosis_bandari.jpg'),
    (['فلافل'], 'branded_felafel.jpg'),
    (['ژامبون', 'کالباس'], 'branded_zhambon_tanoori.jpg'),
    (['ساندویچ مرغ', 'کتلت'], 'branded_sandwich_morgh.jpg'),
    (['قارچ سوخاری', 'توپک'], 'branded_gharch_sookhari.jpg'),
    (['سیب'], 'branded_sib_belgiki.jpg'),
    (['سوخاری', 'فیله', 'کراکت', 'کت وبال'], 'branded_fileh_sookhari.jpg'),
]

def apply_images():
    foods = Food.objects.all().order_by('id')
    total = foods.count()
    updated = 0

    print(f"--- Starting Image Assignment for {total} Foods ---")

    for food in foods:
        image_file = None
        cleaned_name = food.name.strip()

        # 1. Exact Name match
        if cleaned_name in NAME_MAPPING:
            image_file = NAME_MAPPING[cleaned_name]
        # 2. ID match
        elif food.id in ID_MAPPING:
            image_file = ID_MAPPING[food.id]
        # 3. Keyword match
        else:
            lower_name = cleaned_name.lower()
            for keywords, img in KEYWORD_MAPPING:
                if any(kw in lower_name for kw in keywords):
                    image_file = img
                    break

        if image_file:
            relative_path = f"foods/{image_file}"
            food.image = relative_path
            food.save(update_fields=['image'])
            updated += 1
            print(f"[OK] ID {food.id:2d}: {food.name[:25]:<25} -> {relative_path}")
        else:
            print(f"[SKIP] ID {food.id:2d}: {food.name} (no rule matched)")

    print(f"\n--- Finished! Updated {updated}/{total} foods successfully ---")

if __name__ == '__main__':
    apply_images()
