from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from .report_manifest import write_report_manifest
from .storage import read_records
from .types import IntakeRecord


SELECTION_CONFIG = Path("config") / "selection_intelligence.json"
SELECTION_REPORT_PREFIX = "selection_intelligence"


GENERIC_CATEGORY_KEYWORDS = {
    "all",
    "best",
    "buyer",
    "category",
    "departments",
    "homepage",
    "market",
    "new",
    "products",
    "product",
    "radar",
    "release",
    "releases",
    "search",
    "shop",
    "store",
    "trends",
}

CATEGORY_TRANSLATIONS = {
    "all departments": "全部部门",
    "all store": "全店",
    "all marketplace": "全市场",
    "all buyer shop": "买家侧商店",
    "all category radar": "全类目雷达",
    "amazon": "亚马逊",
    "tiktok shop": "TikTok Shop",
    "tiktok": "TikTok",
    "walmart": "沃尔玛",
    "etsy": "Etsy",
    "shein": "SHEIN",
    "temu": "Temu",
    "shopify / dtc": "独立站 / DTC",
    "dtc": "独立站",
    "amazon devices & accessories": "亚马逊设备与配件",
    "appliances": "家用电器",
    "arts, crafts & sewing": "手工、缝纫与DIY",
    "automotive": "汽车用品",
    "baby": "母婴用品",
    "baby & kids": "母婴童",
    "bags & luggage": "箱包",
    "bath & beauty": "沐浴美妆",
    "beauty": "美妆",
    "beauty & personal care": "美妆个护",
    "beauty & personal care products": "美妆个护",
    "books": "图书",
    "camera & photo": "相机摄影",
    "cell phones & accessories": "手机与配件",
    "cell phones accessories": "手机配件",
    "charging & power": "充电与电源",
    "chargers & power adapters": "充电器与电源适配器",
    "clothing": "服装",
    "clothing, shoes & jewelry": "服装、鞋靴与珠宝",
    "computers & accessories": "电脑与配件",
    "electronics": "电子产品",
    "fashion": "服饰",
    "all fashion": "全服饰",
    "women clothing": "女装",
    "men clothing": "男装",
    "menswear": "男装",
    "womenswear": "女装",
    "men": "男士",
    "women": "女士",
    "gender-neutral adult clothing": "中性成人服装",
    "tops": "上衣",
    "tops & tees": "上衣与T恤",
    "tops, tees & blouses": "上衣、T恤与衬衫",
    "shirts": "衬衫",
    "t-shirts": "T恤",
    "hoodies": "卫衣",
    "dresses": "连衣裙",
    "leggings": "打底裤",
    "shorts": "短裤",
    "washed/oversized": "水洗 / 宽松",
    "garment dyed tee": "成衣染色T恤",
    "grocery & gourmet food": "食品饮料",
    "food": "食品",
    "handmade": "手工制品",
    "health": "健康",
    "health & household": "健康家居",
    "health supplements": "营养补剂",
    "supplements": "营养补剂",
    "sleep support": "睡眠支持",
    "melatonin": "褪黑素",
    "magnesium": "镁补剂",
    "creatine": "肌酸",
    "vitamins": "维生素",
    "home": "家居",
    "home & kitchen": "家居厨房",
    "home & living": "家居生活",
    "home supplies": "家居用品",
    "home improvement": "家装",
    "industrial & scientific": "工业与科研",
    "jewelry": "珠宝",
    "jewelry accessories & derivatives": "珠宝配饰",
    "fashion jewelry": "时尚珠宝",
    "kitchen & dining": "厨房餐厨",
    "kitchenware": "厨具",
    "office products": "办公用品",
    "patio & garden": "庭院花园",
    "patio, lawn & garden": "庭院草坪花园",
    "pet supplies": "宠物用品",
    "dogs": "狗用品",
    "sports & outdoors": "运动户外",
    "sports & outdoor": "运动户外",
    "sports": "运动",
    "fitness equipment": "健身器材",
    "tools & home improvement": "工具与家装",
    "toys": "玩具",
    "toys & games": "玩具与游戏",
    "toys & entertainment": "玩具娱乐",
    "video games": "电子游戏",
    "skin care": "护肤",
    "skincare": "护肤",
    "cleanser": "洁面",
    "cleansers": "洁面",
    "face cleanser": "洁面乳",
    "face wash": "洗面奶",
    "moisturizers": "面霜 / 保湿",
    "sunscreen": "防晒",
    "makeup": "彩妆",
    "hair care": "护发",
    "oral care": "口腔护理",
    "amino cleanser": "氨基酸洁面",
    "amino acid cleanser": "氨基酸洗面奶",
    "personal care": "个人护理",
    "mobile phones": "手机",
    "phone accessories": "手机配件",
    "screen protectors": "手机膜 / 屏幕保护膜",
    "phone cases": "手机壳",
    "power banks": "充电宝",
    "portable charger": "便携充电器",
    "cables": "数据线",
    "usb cables": "USB 数据线",
    "audio & headphones": "耳机音频",
    "travel bags": "旅行包",
    "novelty toys": "新奇玩具",
    "car accessories": "汽车配件",
    "storage & organization": "收纳整理",
    "bedding": "床品",
    "bath": "卫浴",
    "cleaning supplies": "清洁用品",
    "outdoor recreation": "户外休闲",
    "fishing": "钓鱼",
    "camping": "露营",
    "tools": "工具",
    "hand tools": "手动工具",
    "power tools": "电动工具",
    "garden": "花园",
    "pet clothing": "宠物服饰",
    "dog supplies": "狗用品",
    "cat supplies": "猫用品",
    "wedding": "婚礼",
    "personalized gifts": "个性化礼物",
    "prints": "印刷品",
    "craft supplies": "手工材料",
    "jewelry & accessories": "珠宝配饰",
    "bags": "包袋",
    "shoes": "鞋靴",
    "sportswear": "运动服",
    "kids": "儿童",
    "underwear & sleepwear": "内衣睡衣",
}


CATEGORY_TRANSLATION_OVERRIDES = {
    "all departments": "全部部门",
    "all store": "全店",
    "all marketplace": "全市场",
    "all buyer shop": "买家侧商店",
    "all category radar": "全类目雷达",
    "amazon": "Amazon",
    "tiktok shop": "TikTok Shop",
    "tiktok": "TikTok",
    "walmart": "Walmart",
    "etsy": "Etsy",
    "shein": "SHEIN",
    "temu": "Temu",
    "shopify / dtc": "独立站 / DTC",
    "dtc": "独立站",
    "amazon devices & accessories": "Amazon 设备与配件",
    "appliances": "家用电器",
    "arts, crafts & sewing": "手工、缝纫与 DIY",
    "automotive": "汽车用品",
    "baby": "母婴用品",
    "baby & kids": "母婴儿童",
    "bags & luggage": "箱包",
    "bath & beauty": "洗护美妆",
    "beauty": "美妆",
    "beauty & personal care": "美妆个护",
    "beauty & personal care products": "美妆个护",
    "books": "图书",
    "camera & photo": "相机摄影",
    "cell phones & accessories": "手机与配件",
    "cell phones accessories": "手机配件",
    "electronics": "电子产品",
    "mobile phones": "手机",
    "phone accessories": "手机配件",
    "screen protectors": "手机膜/屏幕保护膜",
    "phone cases": "手机壳",
    "charging & power": "充电与电源",
    "chargers & power adapters": "充电器与电源适配器",
    "power banks": "充电宝",
    "portable charger": "便携充电器",
    "cables": "数据线",
    "usb cables": "USB 数据线",
    "audio & headphones": "耳机音频",
    "clothing": "服装",
    "clothing, shoes & jewelry": "服装、鞋靴与珠宝",
    "fashion": "时尚",
    "all fashion": "全部时尚",
    "women clothing": "女装",
    "men clothing": "男装",
    "menswear": "男装",
    "womenswear": "女装",
    "men": "男士",
    "women": "女士",
    "gender-neutral adult clothing": "中性成人服装",
    "tops": "上衣",
    "tops & tees": "上衣与 T 恤",
    "tops, tees & blouses": "上衣、T 恤与衬衫",
    "shirts": "衬衫/T恤",
    "t-shirts": "T恤",
    "hoodies": "卫衣",
    "dresses": "连衣裙",
    "leggings": "打底裤",
    "shorts": "短裤",
    "washed/oversized": "水洗/宽松",
    "garment dyed tee": "成衣染色 T 恤",
    "computers & accessories": "电脑与配件",
    "grocery & gourmet food": "食品饮料",
    "food": "食品",
    "handmade": "手工制品",
    "health": "健康",
    "health & household": "健康家居",
    "health supplements": "营养补剂",
    "supplements": "营养补剂",
    "sleep support": "睡眠支持",
    "melatonin": "褪黑素",
    "magnesium": "镁补剂",
    "creatine": "肌酸",
    "vitamins": "维生素",
    "home": "家居",
    "home & kitchen": "家居厨房",
    "home & living": "家居生活",
    "home supplies": "家居用品",
    "home improvement": "家装",
    "industrial & scientific": "工业与科研",
    "kitchen & dining": "厨房餐厨",
    "kitchenware": "厨具",
    "storage & organization": "收纳整理",
    "bedding": "床品",
    "bath": "卫浴",
    "cleaning supplies": "清洁用品",
    "jewelry": "珠宝",
    "jewelry accessories & derivatives": "珠宝配饰",
    "fashion jewelry": "时尚珠宝",
    "jewelry & accessories": "珠宝配饰",
    "office products": "办公用品",
    "patio & garden": "庭院花园",
    "patio, lawn & garden": "庭院草坪花园",
    "pet supplies": "宠物用品",
    "dogs": "狗用品",
    "dog supplies": "狗用品",
    "cat supplies": "猫用品",
    "pet clothing": "宠物服饰",
    "sports & outdoors": "运动户外",
    "sports & outdoor": "运动户外",
    "sports": "运动",
    "outdoor recreation": "户外休闲",
    "fishing": "钓鱼",
    "camping": "露营",
    "fitness equipment": "健身器材",
    "tools & home improvement": "工具与家装",
    "tools": "工具",
    "hand tools": "手动工具",
    "power tools": "电动工具",
    "toys": "玩具",
    "toys & games": "玩具与游戏",
    "toys & entertainment": "玩具娱乐",
    "video games": "电子游戏",
    "skin care": "护肤",
    "skincare": "护肤",
    "cleanser": "洁面",
    "cleansers": "洁面",
    "face cleanser": "洁面乳",
    "face wash": "洗面奶",
    "amino cleanser": "氨基酸洁面",
    "amino acid cleanser": "氨基酸洗面奶",
    "moisturizers": "面霜/保湿",
    "sunscreen": "防晒",
    "makeup": "彩妆",
    "hair care": "护发",
    "oral care": "口腔护理",
    "personal care": "个人护理",
    "travel bags": "旅行包",
    "novelty toys": "新奇玩具",
    "car accessories": "汽车配件",
    "garden": "花园",
    "wedding": "婚礼",
    "personalized gifts": "个性化礼物",
    "prints": "印刷品",
    "craft supplies": "手工材料",
    "bags": "包袋",
    "shoes": "鞋靴",
    "sportswear": "运动服",
    "kids": "儿童",
    "underwear & sleepwear": "内衣睡衣",
}

CATEGORY_TRANSLATION_OVERRIDES.update(
    {
        "ebay": "eBay",
        "shopee": "Shopee",
        "mercado libre": "Mercado Libre",
        "lazada": "Lazada",
        "noon": "Noon",
        "takealot": "Takealot",
        "allegro": "Allegro",
        "coupang": "Coupang",
        "rakuten": "Rakuten",
        "jumia": "Jumia",
        "beauty & health": "美妆健康",
        "health & beauty": "健康美妆",
        "mobile & gadgets": "手机与数码",
        "cell phone screen protectors": "手机膜/屏幕保护膜",
        "computer & office": "电脑办公",
        "consumer electronics": "消费电子",
        "men's fashion": "男装",
        "women's fashion": "女装",
        "household supplies": "家居日用",
        "personal health": "个人健康",
        "dietary supplements": "膳食补充剂",
        "toners": "爽肤水",
        "serums": "精华",
        "masks": "面膜",
        "body care": "身体护理",
        "fragrance": "香水香氛",
        "makeup remover": "卸妆",
        "bathroom": "浴室用品",
        "cleaning tools": "清洁工具",
        "smart watch accessories": "智能手表配件",
        "tablet accessories": "平板配件",
        "car electronics": "车载电子",
        "home appliances": "家用电器",
        "home decor": "家居装饰",
    }
)


def category_segment_translation(segment: str) -> str:
    clean = " ".join(str(segment or "").replace("／", "/").replace("、", "/").split())
    key = clean.lower()
    return CATEGORY_TRANSLATION_OVERRIDES.get(key) or CATEGORY_TRANSLATIONS.get(key) or clean


def category_display_label(category_path: str) -> str:
    raw_parts = [part.strip() for part in str(category_path or "").split(">") if part.strip()]
    if not raw_parts:
        return ""
    translated_parts = [category_segment_translation(part) for part in raw_parts]
    translated = " > ".join(translated_parts)
    raw = " > ".join(raw_parts)
    if translated.lower() == raw.lower():
        return raw
    return f"{translated} / {raw}"


DEFAULT_CATEGORY_FILTER_PATHS: tuple[str, ...] = (
    "Amazon > All Departments",
    "Amazon > Amazon Devices & Accessories",
    "Amazon > Appliances",
    "Amazon > Arts, Crafts & Sewing",
    "Amazon > Automotive",
    "Amazon > Baby",
    "Amazon > Beauty & Personal Care",
    "Amazon > Beauty & Personal Care > Skin Care",
    "Amazon > Beauty & Personal Care > Skin Care > Cleansers",
    "Amazon > Beauty & Personal Care > Skin Care > Cleansers > Face Wash",
    "Amazon > Beauty & Personal Care > Skin Care > Cleansers > Face Wash > Amino Acid Cleanser",
    "Amazon > Beauty & Personal Care > Skin Care > Moisturizers",
    "Amazon > Beauty & Personal Care > Skin Care > Sunscreen",
    "Amazon > Beauty & Personal Care > Makeup",
    "Amazon > Beauty & Personal Care > Hair Care",
    "Amazon > Books",
    "Amazon > Camera & Photo",
    "Amazon > Cell Phones & Accessories",
    "Amazon > Electronics",
    "Amazon > Electronics > Cell Phones & Accessories",
    "Amazon > Electronics > Cell Phones & Accessories > Phone Accessories",
    "Amazon > Electronics > Cell Phones & Accessories > Phone Accessories > Screen Protectors",
    "Amazon > Electronics > Cell Phones & Accessories > Phone Accessories > Phone Cases",
    "Amazon > Electronics > Cell Phones & Accessories > Charging & Power",
    "Amazon > Electronics > Cell Phones & Accessories > Charging & Power > Power Banks",
    "Amazon > Electronics > Cell Phones & Accessories > Charging & Power > Cables",
    "Amazon > Electronics > Audio & Headphones",
    "Amazon > Clothing, Shoes & Jewelry",
    "Amazon > Fashion > Men > Clothing > Shirts > T-Shirts",
    "Amazon > Fashion > Women > Clothing > Tops, Tees & Blouses > T-Shirts",
    "Amazon > Grocery & Gourmet Food",
    "Amazon > Handmade",
    "Amazon > Health & Household",
    "Amazon > Health & Household > Health Supplements",
    "Amazon > Health & Household > Health Supplements > Sleep Support > Melatonin",
    "Amazon > Health & Household > Health Supplements > Magnesium",
    "Amazon > Health & Household > Health Supplements > Creatine",
    "Amazon > Home & Kitchen",
    "Amazon > Home & Kitchen > Kitchen & Dining",
    "Amazon > Home & Kitchen > Storage & Organization",
    "Amazon > Home & Kitchen > Bedding",
    "Amazon > Industrial & Scientific",
    "Amazon > Office Products",
    "Amazon > Patio, Lawn & Garden",
    "Amazon > Pet Supplies",
    "Amazon > Pet Supplies > Dogs",
    "Amazon > Sports & Outdoors",
    "Amazon > Sports & Outdoors > Fitness Equipment",
    "Amazon > Sports & Outdoors > Outdoor Recreation > Fishing",
    "Amazon > Tools & Home Improvement",
    "Amazon > Toys & Games",
    "Amazon > Video Games",
    "TikTok Shop > All Buyer Shop",
    "TikTok Shop > Beauty & Personal Care",
    "TikTok Shop > Beauty & Personal Care > Skin Care",
    "TikTok Shop > Beauty & Personal Care > Skin Care > Cleansers",
    "TikTok Shop > Beauty & Personal Care > Skin Care > Cleansers > Amino Cleanser",
    "TikTok Shop > Beauty & Personal Care > Makeup",
    "TikTok Shop > Beauty & Personal Care > Hair Care",
    "TikTok Shop > Health",
    "TikTok Shop > Health > Supplements",
    "TikTok Shop > Health > Supplements > Melatonin",
    "TikTok Shop > Health > Supplements > Magnesium",
    "TikTok Shop > Fashion",
    "TikTok Shop > Fashion > Menswear",
    "TikTok Shop > Fashion > Menswear > Tops",
    "TikTok Shop > Fashion > Menswear > Tops > T-Shirts",
    "TikTok Shop > Fashion > Womenswear",
    "TikTok Shop > Fashion > Womenswear > Tops",
    "TikTok Shop > Fashion > Womenswear > Tops > T-Shirts",
    "TikTok Shop > Electronics",
    "TikTok Shop > Electronics > Phone Accessories",
    "TikTok Shop > Electronics > Phone Accessories > Screen Protectors",
    "TikTok Shop > Electronics > Phone Accessories > Phone Cases",
    "TikTok Shop > Electronics > Charging & Power",
    "TikTok Shop > Electronics > Charging & Power > Power Banks",
    "TikTok Shop > Home & Living",
    "TikTok Shop > Home & Living > Storage & Organization",
    "TikTok Shop > Pet Supplies",
    "TikTok Shop > Sports & Outdoors",
    "TikTok Shop > Tools & Home Improvement",
    "Walmart > All Departments",
    "Walmart > Beauty",
    "Walmart > Beauty > Skin Care > Cleansers",
    "Walmart > Health",
    "Walmart > Health > Vitamins > Melatonin",
    "Walmart > Electronics",
    "Walmart > Electronics > Cell Phones Accessories > Screen Protectors",
    "Walmart > Electronics > Charging & Power > Power Banks",
    "Walmart > Clothing",
    "Walmart > Clothing > Men Clothing > T-Shirts",
    "Walmart > Clothing > Women Clothing > T-Shirts",
    "Walmart > Home",
    "Walmart > Home > Kitchenware",
    "Walmart > Sports & Outdoors",
    "Walmart > Pets",
    "Etsy > All Marketplace",
    "Etsy > Handmade",
    "Etsy > Clothing",
    "Etsy > Clothing > T-Shirts",
    "Etsy > Jewelry",
    "Etsy > Jewelry & Accessories",
    "Etsy > Wedding",
    "Etsy > Personalized Gifts",
    "Etsy > Craft Supplies",
    "Etsy > Prints",
    "SHEIN > All Fashion",
    "SHEIN > Women Clothing",
    "SHEIN > Women Clothing > Tops",
    "SHEIN > Women Clothing > Dresses",
    "SHEIN > Men Clothing",
    "SHEIN > Men Clothing > Tops",
    "SHEIN > Sportswear",
    "SHEIN > Beauty",
    "SHEIN > Home Supplies",
    "SHEIN > Pet Supplies",
    "Temu > All Marketplace",
    "Temu > Electronics",
    "Temu > Electronics > Phone Accessories",
    "Temu > Electronics > Phone Accessories > Screen Protectors",
    "Temu > Beauty & Health",
    "Temu > Beauty & Health > Skin Care",
    "Temu > Clothing",
    "Temu > Clothing > T-Shirts",
    "Temu > Home & Kitchen",
    "Temu > Tools & Home Improvement",
    "Shopify / DTC > All Store",
    "Shopify / DTC > Beauty & Personal Care",
    "Shopify / DTC > Fashion",
    "Shopify / DTC > Electronics",
    "Shopify / DTC > Home & Living",
)

EXTENDED_CATEGORY_FILTER_PATHS: tuple[str, ...] = (
    "eBay > All Marketplace",
    "eBay > Health & Beauty",
    "eBay > Health & Beauty > Skin Care",
    "eBay > Cell Phones & Accessories",
    "eBay > Cell Phones & Accessories > Cell Phone Screen Protectors",
    "eBay > Clothing, Shoes & Accessories",
    "eBay > Clothing, Shoes & Accessories > Men's Fashion > T-Shirts",
    "eBay > Clothing, Shoes & Accessories > Women's Fashion > T-Shirts",
    "eBay > Home & Garden",
    "eBay > Sporting Goods",
    "Shopee > All Marketplace",
    "Shopee > Beauty",
    "Shopee > Beauty > Skincare",
    "Shopee > Beauty > Skincare > Cleansers",
    "Shopee > Health",
    "Shopee > Health > Dietary Supplements",
    "Shopee > Fashion",
    "Shopee > Men's Fashion",
    "Shopee > Women's Fashion",
    "Shopee > Mobile & Gadgets",
    "Shopee > Mobile & Gadgets > Phone Accessories > Screen Protectors",
    "Shopee > Home & Living",
    "Shopee > Mom & Baby",
    "Mercado Libre > All Marketplace",
    "Mercado Libre > Beauty & Personal Care",
    "Mercado Libre > Beauty & Personal Care > Skin Care",
    "Mercado Libre > Health",
    "Mercado Libre > Cell Phones & Accessories",
    "Mercado Libre > Cell Phones & Accessories > Screen Protectors",
    "Mercado Libre > Clothing",
    "Mercado Libre > Home & Garden",
    "Lazada > All Marketplace",
    "Lazada > Beauty",
    "Lazada > Beauty > Skin Care",
    "Lazada > Health",
    "Lazada > Fashion",
    "Lazada > Electronics",
    "Lazada > Electronics > Mobile Accessories > Screen Protectors",
    "Lazada > Home & Living",
    "Noon > All Marketplace",
    "Noon > Beauty",
    "Noon > Electronics",
    "Noon > Fashion",
    "Takealot > All Marketplace",
    "Takealot > Beauty",
    "Takealot > Electronics",
    "Takealot > Fashion",
    "Coupang > All Marketplace",
    "Coupang > Beauty",
    "Coupang > Health",
    "Coupang > Electronics",
    "Rakuten > All Marketplace",
    "Rakuten > Beauty",
    "Rakuten > Fashion",
    "Allegro > All Marketplace",
    "Allegro > Beauty",
    "Allegro > Electronics",
    "Jumia > All Marketplace",
    "Jumia > Beauty",
    "Jumia > Phones & Tablets",
)

DEFAULT_CATEGORY_FILTER_PATHS = tuple(dict.fromkeys((*DEFAULT_CATEGORY_FILTER_PATHS, *EXTENDED_CATEGORY_FILTER_PATHS)))


@dataclass(slots=True)
class CategoryNode:
    platform: str
    path: list[str]
    depth: int
    url: str
    ranking_types: list[str]
    enabled: bool = True

    @property
    def category_path(self) -> str:
        return " > ".join(self.path)


@dataclass(slots=True)
class SelectionIntelligenceResult:
    run_date: str
    categories: list[CategoryNode]
    movements: list[dict[str, Any]]
    new_release_candidates: list[dict[str, Any]]
    category_recommendations: list[dict[str, Any]]
    platform_rankings: dict[str, list[dict[str, Any]]]
    report: str
    report_path: Path
    json_path: Path
    manifest_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "categories": [
                {
                    "platform": item.platform,
                    "path": item.path,
                    "depth": item.depth,
                    "url": item.url,
                    "ranking_types": item.ranking_types,
                    "enabled": item.enabled,
                }
                for item in self.categories
            ],
            "movements": self.movements,
            "new_release_candidates": self.new_release_candidates,
            "category_recommendations": self.category_recommendations,
            "platform_rankings": self.platform_rankings,
            "report": self.report,
            "report_path": str(self.report_path),
            "json_path": str(self.json_path),
            "manifest_path": str(self.manifest_path),
        }


def run_selection_intelligence(root: Path, run_date: str | None = None) -> SelectionIntelligenceResult:
    root = root.resolve()
    report_date = run_date or date.today().isoformat()
    config = load_selection_config(root)
    categories = load_category_nodes(config)
    raw_records = read_records(root, "platform_ranking_signal")
    records = [
        record
        for record in raw_records
        if not is_verification_page_record(record) and not is_empty_or_weak_selection_record(record)
    ]
    movements = detect_ranking_movements(records)
    new_releases = detect_new_release_candidates(records)
    category_recommendations = score_category_products(records, categories, movements, new_releases)
    platform_rankings = build_platform_rankings(category_recommendations)
    report = build_selection_report(report_date, config, categories, movements, new_releases, category_recommendations, platform_rankings)
    report_path = write_selection_report(root, report_date, report)
    json_path = write_selection_json(root, report_date, categories, movements, new_releases, category_recommendations, platform_rankings)
    manifest_path = write_report_manifest(
        root,
        "selection_intelligence",
        report_date,
        {"markdown": report_path, "json": json_path},
        records,
        parser_version="selection_intelligence_v1",
        scope={
            "monitored_category_count": len(categories),
            "platforms": sorted({category.platform for category in categories}),
        },
        exclusion_summary={
            "platform_ranking_signal_read": len(raw_records),
            "platform_ranking_signal_used": len(records),
            "verification_or_weak_records_excluded": len(raw_records) - len(records),
        },
        seller_safe_summary={
            "decision": "Category ranking and product watchlist generated.",
            "evidence_gap": "Missing marketplace price, reviews, supplier cost, or TikTok content evidence should block scale-up.",
            "next_step": "Use the ranked candidates as WATCH inputs for the AI selection meeting.",
        },
    )
    return SelectionIntelligenceResult(
        report_date,
        categories,
        movements,
        new_releases,
        category_recommendations,
        platform_rankings,
        report,
        report_path,
        json_path,
        manifest_path,
    )


def load_selection_config(root: Path) -> dict[str, Any]:
    path = root / SELECTION_CONFIG
    if not path.exists():
        return default_selection_config()
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        return default_selection_config()
    payload.setdefault("platforms", default_selection_config()["platforms"])
    payload.setdefault("monitoring", default_selection_config()["monitoring"])
    return payload


def default_selection_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "notes": [
            "Category tree is the backbone of product selection. Keep platform, category depth, ranking URLs, and ranking type together.",
            "Rank monitoring compares the newest record with older records for the same product and ranking context.",
            "Sensitive actions are not executed automatically; this module only reports opportunities."
        ],
        "monitoring": {
            "sudden_growth_rank_improvement": 20,
            "top_rank_threshold": 30,
            "watch_ranking_types": ["Best Sellers", "New Releases", "Movers & Shakers", "Keyword Search", "Buyer Video / Product Card"]
        },
        "platforms": [
            {
                "platform": "Amazon",
                "enabled": True,
                "categories": [
                    {
                        "path": ["All Store", "Fashion", "Clothing, Shoes & Jewelry"],
                        "url": "https://www.amazon.com/Best-Sellers-Fashion/zgbs/fashion/",
                        "ranking_types": ["Best Sellers", "New Releases", "Movers & Shakers"]
                    },
                    {
                        "path": ["Fashion", "Men", "Clothing", "Shirts", "T-Shirts"],
                        "url": "https://www.amazon.com/s?k=mens+washed+t+shirt",
                        "ranking_types": ["Keyword Search", "Best Sellers", "New Releases"]
                    },
                    {
                        "path": ["Fashion", "Women", "Clothing", "Tops", "T-Shirts"],
                        "url": "https://www.amazon.com/s?k=womens+washed+t+shirt",
                        "ranking_types": ["Keyword Search", "Best Sellers", "New Releases"]
                    }
                ]
            },
            {
                "platform": "TikTok Shop",
                "enabled": True,
                "categories": [
                    {
                        "path": ["TikTok Shop", "Fashion", "Menswear", "Tops", "T-Shirts"],
                        "url": "https://shop.tiktok.com/us?source=product_detail&enter_method=left_panel_logo&first_entrance=video_detail&first_entrance_position=product_card&first_entrance_tt_scene=tt_seo",
                        "ranking_types": ["Buyer Video / Product Card", "Shop Search", "Viral Product"]
                    },
                    {
                        "path": ["TikTok", "Video", "Fashion Content", "Washed Tee"],
                        "url": "https://www.tiktok.com/search?q=washed%20t%20shirt",
                        "ranking_types": ["Video Search", "Viral Content"]
                    }
                ]
            },
            {
                "platform": "Etsy",
                "enabled": True,
                "categories": [
                    {
                        "path": ["Etsy", "Clothing", "Gender-Neutral Adult Clothing", "Tops & Tees", "T-Shirts"],
                        "url": "https://www.etsy.com/search?q=washed%20t%20shirt",
                        "ranking_types": ["Keyword Search", "Bestseller Badges", "New Listings"]
                    }
                ]
            },
            {
                "platform": "Walmart",
                "enabled": True,
                "categories": [
                    {
                        "path": ["Walmart", "Clothing", "Men", "Mens Shirts", "T-Shirts"],
                        "url": "https://www.walmart.com/search?q=washed%20t%20shirt",
                        "ranking_types": ["Keyword Search", "Best Match", "Best Seller"]
                    }
                ]
            },
            {
                "platform": "SHEIN",
                "enabled": True,
                "categories": [
                    {
                        "path": ["SHEIN", "Men Clothing", "Tops", "T-Shirts", "Washed/Oversized"],
                        "url": "https://us.shein.com/pdsearch/washed%20t%20shirt/",
                        "ranking_types": ["Search Ranking", "New In", "Trending"]
                    }
                ]
            },
            {
                "platform": "Temu",
                "enabled": True,
                "categories": [
                    {
                        "path": ["Temu", "Mens Clothing", "Tops", "T-Shirts", "Washed/Oversized"],
                        "url": "https://www.temu.com/search_result.html?search_key=washed%20t%20shirt",
                        "ranking_types": ["Search Ranking", "New Arrivals", "Popular"]
                    }
                ]
            },
            {
                "platform": "Shopify / DTC",
                "enabled": True,
                "categories": [
                    {
                        "path": ["DTC", "Apparel Brand", "Tops", "Garment Dyed Tee"],
                        "url": "https://www.google.com/search?q=washed+t+shirt+shopify+brand",
                        "ranking_types": ["Google Competitor Search", "DTC Collection"]
                    }
                ]
            }
        ]
    }


def load_category_nodes(config: dict[str, Any]) -> list[CategoryNode]:
    nodes: list[CategoryNode] = []
    for platform_config in config.get("platforms", []):
        if not isinstance(platform_config, dict) or not platform_config.get("enabled", True):
            continue
        platform = str(platform_config.get("platform") or "Unknown")
        for raw in platform_config.get("categories", []):
            if not isinstance(raw, dict):
                continue
            path = raw.get("path") if isinstance(raw.get("path"), list) else []
            clean_path = [str(item).strip() for item in path if str(item).strip()]
            if not clean_path:
                continue
            ranking_types = raw.get("ranking_types") if isinstance(raw.get("ranking_types"), list) else []
            nodes.append(
                CategoryNode(
                    platform=platform,
                    path=clean_path,
                    depth=len(clean_path),
                    url=str(raw.get("url") or ""),
                    ranking_types=[str(item) for item in ranking_types if str(item).strip()],
                    enabled=bool(raw.get("enabled", True)),
                )
            )
    return nodes


def default_ranking_types_for_platform(platform: str) -> list[str]:
    normalized = platform.lower()
    if "tiktok" in normalized:
        return ["Buyer Product Search", "Viral Product", "Video Evidence"]
    if "amazon" in normalized:
        return ["Keyword Search", "Best Sellers", "New Releases"]
    if "fastmoss" in normalized or "kalodata" in normalized:
        return ["Product Ranking", "Creator Ranking", "Video Ranking"]
    return ["Keyword Search", "Best Match", "Trending"]


def category_search_query(path: list[str]) -> str:
    useful_parts = [
        part
        for part in path[1:]
        if part.lower() not in {"all departments", "all marketplace", "all store", "all buyer shop", "all fashion"}
    ]
    query_parts = useful_parts[-3:] if useful_parts else path[-2:]
    return " ".join(query_parts).strip() or "top products"


def default_category_url(platform: str, path: list[str]) -> str:
    query = quote_plus(category_search_query(path))
    normalized = platform.lower()
    if "amazon" in normalized:
        return f"https://www.amazon.com/s?k={query}"
    if "tiktok" in normalized:
        return f"https://shop.tiktok.com/us/search?keyword={query}"
    if "walmart" in normalized:
        return f"https://www.walmart.com/search?q={query}"
    if "etsy" in normalized:
        return f"https://www.etsy.com/search?q={query}"
    if "shein" in normalized:
        return f"https://us.shein.com/pdsearch/{query}/"
    if "temu" in normalized:
        return f"https://www.temu.com/search_result.html?search_key={query}"
    if "ebay" in normalized:
        return f"https://www.ebay.com/sch/i.html?_nkw={query}"
    if "shopee" in normalized:
        return f"https://shopee.com/search?keyword={query}"
    if "mercado libre" in normalized:
        return f"https://listado.mercadolibre.com/{query}"
    if "lazada" in normalized:
        return f"https://www.lazada.com/catalog/?q={query}"
    if "noon" in normalized:
        return f"https://www.noon.com/search/?q={query}"
    if "takealot" in normalized:
        return f"https://www.takealot.com/all?qsearch={query}"
    if "coupang" in normalized:
        return f"https://www.coupang.com/np/search?q={query}"
    if "rakuten" in normalized:
        return f"https://search.rakuten.co.jp/search/mall/{query}/"
    if "allegro" in normalized:
        return f"https://allegro.pl/listing?string={query}"
    if "jumia" in normalized:
        return f"https://www.jumia.com/catalog/?q={query}"
    return f"https://www.google.com/search?q={query}+ecommerce+best+sellers"


def default_category_nodes_from_filter_paths() -> list[CategoryNode]:
    nodes: list[CategoryNode] = []
    for raw_path in DEFAULT_CATEGORY_FILTER_PATHS:
        path = [part.strip() for part in raw_path.split(">") if part.strip()]
        if len(path) < 2:
            continue
        platform = path[0]
        nodes.append(
            CategoryNode(
                platform=platform,
                path=path,
                depth=len(path),
                url=default_category_url(platform, path),
                ranking_types=default_ranking_types_for_platform(platform),
                enabled=True,
            )
        )
    return nodes


def build_selection_category_sources(root: Path) -> list[dict[str, Any]]:
    has_custom_config = (root / SELECTION_CONFIG).exists()
    config = load_selection_config(root)
    if not config.get("enabled", True):
        return []
    nodes = load_category_nodes(config)
    if not has_custom_config:
        seen = {node.category_path for node in nodes}
        for node in default_category_nodes_from_filter_paths():
            if node.category_path not in seen:
                nodes.append(node)
                seen.add(node.category_path)
    sources: list[dict[str, Any]] = []
    for node in nodes:
        if not node.enabled or not node.url:
            continue
        safe_id = category_source_safe_id(node)
        ranking_type = " / ".join(node.ranking_types[:2]) if node.ranking_types else "Category Ranking"
        sources.append(
            {
                "id": f"selection-category-{safe_id}",
                "name": f"{node.platform} / {node.category_path}",
                "enabled": True,
                "record_type": "platform_ranking_signal",
                "platform": node.platform,
                "source_platform": node.platform,
                "marketplace": node.platform,
                "ranking_type": ranking_type,
                "url": node.url,
                "expected_keywords": expected_keywords_for_category(node),
                "category_path": node.category_path,
                "category_depth": node.depth,
                "data_category": "selection_category_ranking",
                "monitoring_scope": "category_tree",
                "notes": "Selection Intelligence category-tree ranking source.",
            }
        )
    return sources


def expected_keywords_for_category(node: CategoryNode) -> list[str]:
    keywords: list[str] = []
    for part in node.path[-3:]:
        for token in part.replace("/", " ").replace("&", " ").split():
            clean = token.strip(" ,.-").lower()
            if (
                clean
                and len(clean) >= 4
                and clean not in {"shopify", "amazon", "tiktok", "walmart", "shein", "temu"}
                and clean not in GENERIC_CATEGORY_KEYWORDS
            ):
                keywords.append(clean)
    return keywords[:5]


def category_source_safe_id(node: CategoryNode) -> str:
    raw = "-".join([node.platform, *node.path]).lower()
    return "".join(char if char.isalnum() else "-" for char in raw).strip("-")[:90]


def detect_ranking_movements(records: list[IntakeRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[IntakeRecord]] = {}
    for record in records:
        key = movement_key(record)
        if not key:
            continue
        grouped.setdefault(key, []).append(record)
    movements: list[dict[str, Any]] = []
    for key, items in grouped.items():
        if len(items) < 2:
            continue
        sorted_items = sorted(items, key=lambda item: item.created_at)
        previous = sorted_items[-2]
        latest = sorted_items[-1]
        previous_rank = parse_rank(previous.fields.get("rank_position"))
        latest_rank = parse_rank(latest.fields.get("rank_position"))
        if previous_rank is None or latest_rank is None:
            continue
        improvement = previous_rank - latest_rank
        if improvement == 0:
            continue
        fields = latest.fields
        movements.append(
            {
                "key": key,
                "platform": fields.get("marketplace") or fields.get("source_platform") or "",
                "ranking_type": fields.get("ranking_type") or "",
                "category_path": fields.get("category_path") or "",
                "product_name": fields.get("product_name") or "",
                "url": fields.get("url") or "",
                "previous_rank": previous_rank,
                "latest_rank": latest_rank,
                "rank_improvement": improvement,
                "direction": "up" if improvement > 0 else "down",
                "latest_record_id": latest.record_id,
                "previous_record_id": previous.record_id,
                "latest_at": latest.created_at,
            }
        )
    return sorted(movements, key=lambda item: (item["rank_improvement"], -item["latest_rank"]), reverse=True)


def detect_new_release_candidates(records: list[IntakeRecord]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: item.created_at, reverse=True):
        fields = record.fields
        ranking_type = str(fields.get("ranking_type") or "").lower()
        if not any(signal in ranking_type for signal in ["new release", "new releases", "new in", "new arrivals", "新品"]):
            continue
        rank = parse_rank(fields.get("rank_position"))
        candidates.append(
            {
                "platform": fields.get("marketplace") or fields.get("source_platform") or "",
                "ranking_type": fields.get("ranking_type") or "",
                "category_path": fields.get("category_path") or "",
                "product_name": fields.get("product_name") or "",
                "rank_position": rank,
                "url": fields.get("url") or "",
                "record_id": record.record_id,
                "created_at": record.created_at,
            }
        )
    return candidates[:40]


def score_category_products(
    records: list[IntakeRecord],
    categories: list[CategoryNode],
    movements: list[dict[str, Any]],
    new_releases: list[dict[str, Any]],
    limit_per_category: int = 5,
) -> list[dict[str, Any]]:
    movement_by_id = {
        str(item.get("latest_record_id") or ""): item
        for item in movements
        if item.get("latest_record_id")
    }
    new_release_ids = {str(item.get("record_id") or "") for item in new_releases}
    product_records = [
        record
        for record in records
        if record_product_name(record)
        and record_url(record)
        and not is_verification_page_record(record)
        and not is_empty_or_weak_selection_record(record)
    ]
    recommendations: list[dict[str, Any]] = []
    for category in categories:
        scored: list[dict[str, Any]] = []
        seen: set[str] = set()
        for record in product_records:
            if not record_matches_category(record, category):
                continue
            key = record_product_key(record)
            if key in seen:
                continue
            seen.add(key)
            movement = movement_by_id.get(record.record_id)
            is_new_release = record.record_id in new_release_ids or is_new_release_record(record)
            score, reasons = score_product_for_category(record, category, movement, is_new_release)
            scored.append(
                {
                    "platform": category.platform,
                    "category_path": category.category_path,
                    "category_depth": category.depth,
                    "product_name": record_product_name(record),
                    "rank_position": parse_rank(record.fields.get("rank_position")),
                    "ranking_type": record.fields.get("ranking_type") or "",
                    "url": record_url(record),
                    "record_id": record.record_id,
                    "score": score,
                    "reasons": reasons,
                    "recommendation": category_recommendation_label(score, reasons),
                    "ai_meeting_prompt": build_category_meeting_prompt(category, record, score, reasons),
                }
            )
        for item in sorted(scored, key=lambda value: (float(value.get("score") or 0), -(value.get("rank_position") or 9999)), reverse=True)[:limit_per_category]:
            recommendations.append(item)
    return recommendations


def record_matches_category(record: IntakeRecord, category: CategoryNode) -> bool:
    if is_verification_page_record(record):
        return False
    fields = record.fields
    data_category = str(fields.get("data_category") or "").lower()
    monitoring_scope = str(fields.get("monitoring_scope") or "").lower()
    if data_category == "brand_marketplace_search" or monitoring_scope == "brand_target":
        return False
    platform = str(fields.get("marketplace") or fields.get("source_platform") or "").lower()
    if category.platform.lower() not in platform and platform not in category.platform.lower():
        return False
    automation_source_id = ""
    if isinstance(record.metadata, dict):
        automation_source_id = str(record.metadata.get("automation_source_id") or "")
    if automation_source_id.startswith("selection-category-"):
        return automation_source_id == f"selection-category-{category_source_safe_id(category)}"
    haystack = " ".join(
        str(fields.get(key) or "")
        for key in ["category_path", "ranking_page", "url", "page_url", "product_name", "page_title", "visible_growth_signal"]
    ).lower()
    if category_requires_cleanser_match(category) and not record_looks_like_cleanser(record):
        return False
    if category_requires_apparel_match(category) and record_looks_like_cleanser(record):
        return False
    if category.url and category.url.lower() in haystack:
        return True
    category_path = category.category_path.lower()
    if category_path and category_path in haystack:
        return True
    keywords = expected_keywords_for_category(category)
    if not keywords:
        return False
    return any(keyword in haystack for keyword in keywords)


def category_requires_cleanser_match(category: CategoryNode) -> bool:
    category_text = category.category_path.lower()
    return any(term in category_text for term in ["cleanser", "face wash", "skin care", "skincare", "beauty"])


def category_requires_apparel_match(category: CategoryNode) -> bool:
    category_text = category.category_path.lower()
    return any(term in category_text for term in ["t-shirt", "shirts", "tops", "clothing", "apparel", "fashion"])


def record_looks_like_cleanser(record: IntakeRecord) -> bool:
    haystack = json.dumps(record.fields, ensure_ascii=False).lower()
    cleanser_terms = ["cleanser", "face wash", "facial wash", "cleansing foam", "cleansing gel", "skincare", "skin care", "foaming facial"]
    apparel_terms = ["t-shirt", "tshirt", "tee", "shirts", "oversized", "cotton", "garment dyed", "acid wash"]
    cleanser_hits = sum(1 for term in cleanser_terms if term in haystack)
    apparel_hits = sum(1 for term in apparel_terms if term in haystack)
    return cleanser_hits > 0 and cleanser_hits >= apparel_hits


def is_verification_page_record(record: IntakeRecord) -> bool:
    fields = record.fields or {}
    haystack = " ".join(
        str(fields.get(key) or "")
        for key in [
            "product_name",
            "page_title",
            "page_text",
            "visible_growth_signal",
            "url",
        ]
    ).lower()
    return any(
        signal in haystack
        for signal in [
            "security check",
            "captcha",
            "verify to continue",
            "verify you are human",
            "drag the puzzle",
            "slider",
            "verification",
            "安全验证",
            "验证码",
            "滑块",
            "请完成验证",
        ]
    )


def is_empty_or_weak_selection_record(record: IntakeRecord) -> bool:
    fields = record.fields or {}
    metadata = record.metadata or {}
    haystack = json.dumps(fields, ensure_ascii=False).lower()
    if any(signal in haystack for signal in ["暂无数据", "\u6682\u65e0\u6570\u636e", "loading", "no data", "not found"]):
        return True
    validation = metadata.get("platform_autopilot_validation") if isinstance(metadata, dict) else None
    product_match = metadata.get("product_match") if isinstance(metadata, dict) else None
    if isinstance(validation, dict) and validation.get("status") == "needs_review":
        return True
    if isinstance(product_match, dict) and product_match.get("status") == "different_product":
        return True
    source_text = " ".join(str(fields.get(key) or "") for key in ["source_platform", "marketplace", "page_title"]).lower()
    if any(tool in source_text for tool in ["fastmoss", "kalodata"]):
        has_real_metric = any(
            str(fields.get(key) or "").strip()
            for key in ["rank_position", "sales", "gmv", "creator_handle", "video_url", "product_url", "product_asin"]
        )
        if not has_real_metric:
            return True
    return False


def score_product_for_category(
    record: IntakeRecord,
    category: CategoryNode,
    movement: dict[str, Any] | None,
    is_new_release: bool,
) -> tuple[int, list[str]]:
    fields = record.fields
    score = 20
    reasons: list[str] = []
    rank = parse_rank(fields.get("rank_position"))
    if rank:
        rank_points = max(0, 35 - min(rank, 100) // 3)
        score += rank_points
        reasons.append(f"rank #{rank}")
        if rank <= 10:
            reasons.append("top 10")
    priority = record.score.get("priority")
    try:
        score += min(5, max(0, int(float(priority)) - 70) // 6)
    except (TypeError, ValueError):
        pass
    ranking_type = str(fields.get("ranking_type") or "").lower()
    if is_new_release:
        score += 10
        reasons.append("new release signal")
    if any(word in ranking_type for word in ["best sellers", "bsr", "top"]):
        score += 8
        reasons.append("best-seller list")
    if any(word in ranking_type for word in ["mover", "growth", "viral"]):
        score += 10
        reasons.append("growth list")
    if movement:
        improvement = int(movement.get("rank_improvement") or 0)
        if improvement > 0:
            score += min(18, improvement // 2)
            reasons.append(f"rank improved +{improvement}")
    keyword_hits = category_keyword_hits(record, category)
    if keyword_hits:
        score += min(10, len(keyword_hits) * 3)
        reasons.append("category match: " + ", ".join(keyword_hits[:3]))
    evidence = strict_selection_evidence(record, category, movement, is_new_release, keyword_hits)
    score += min(18, evidence["count"] * 3)
    if evidence["labels"]:
        reasons.append("evidence: " + ", ".join(evidence["labels"][:4]))
    if looks_like_brand_locked(record):
        score -= 14
        reasons.append("brand/IP caution")
    score = apply_strict_selection_caps(score, record, rank, keyword_hits, evidence, movement, is_new_release)
    reasons.append(f"strict grade {strict_selection_grade(score)}")
    return max(0, min(100, score)), reasons[:9]


def strict_selection_evidence(
    record: IntakeRecord,
    category: CategoryNode,
    movement: dict[str, Any] | None,
    is_new_release: bool,
    keyword_hits: list[str],
) -> dict[str, Any]:
    fields = record.fields or {}
    labels: list[str] = []
    if parse_rank(fields.get("rank_position")):
        labels.append("rank")
    if keyword_hits or record_matches_category(record, category):
        labels.append("category")
    if movement or is_new_release:
        labels.append("growth/new")
    if any(str(fields.get(key) or "").strip() for key in ["sales", "sales_count", "item_sold_count", "gmv", "revenue", "price"]):
        labels.append("sales/price")
    if any(str(fields.get(key) or "").strip() for key in ["review_count", "rating", "comment_count", "review_text"]):
        labels.append("review")
    if any(str(fields.get(key) or "").strip() for key in ["video_url", "creator_handle", "creator_name", "influencer_handle"]):
        labels.append("video/creator")
    if record_url(record):
        labels.append("link")
    return {"count": len(set(labels)), "labels": list(dict.fromkeys(labels))}


def apply_strict_selection_caps(
    score: int,
    record: IntakeRecord,
    rank: int | None,
    keyword_hits: list[str],
    evidence: dict[str, Any],
    movement: dict[str, Any] | None,
    is_new_release: bool,
) -> int:
    fields = record.fields or {}
    labels = set(evidence.get("labels") or [])
    platform = str(fields.get("marketplace") or fields.get("source_platform") or record.source or "").lower()
    capped = score
    if "link" not in labels:
        capped = min(capped, 45)
    if not rank and "sales/price" not in labels:
        capped = min(capped, 54)
    if not keyword_hits:
        capped = min(capped, 72)
    if not movement and not is_new_release and (not rank or rank > 10):
        capped = min(capped, 76)
    if any(token in platform for token in ["tiktok", "fastmoss", "kalodata"]) and not ({"video/creator", "review", "sales/price"} & labels):
        capped = min(capped, 70)
    if looks_like_brand_locked(record):
        capped = min(capped, 69)
    if capped >= 90 and len(labels) < 5:
        capped = 89
    if capped >= 85 and not (rank and rank <= 30):
        capped = 84
    return int(capped)


def strict_selection_grade(score: int) -> str:
    if score >= 90:
        return "S"
    if score >= 82:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def build_platform_rankings(category_recommendations: list[dict[str, Any]], limit_per_platform: int = 20) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in category_recommendations:
        platform = str(item.get("platform") or "Unknown")
        grouped.setdefault(platform, []).append(item)
    rankings: dict[str, list[dict[str, Any]]] = {}
    for platform, items in grouped.items():
        ordered = sorted(
            items,
            key=lambda item: (
                int(item.get("score") or 0),
                -(int(item.get("rank_position") or 9999)),
                str(item.get("product_name") or ""),
            ),
            reverse=True,
        )[:limit_per_platform]
        rankings[platform] = [
            {
                **item,
                "platform_rank": index,
                "strict_grade": strict_selection_grade(int(item.get("score") or 0)),
            }
            for index, item in enumerate(ordered, 1)
        ]
    return dict(sorted(rankings.items(), key=lambda pair: selection_platform_priority(pair[0])))


def category_keyword_hits(record: IntakeRecord, category: CategoryNode) -> list[str]:
    haystack = json.dumps(record.fields, ensure_ascii=False).lower()
    return [keyword for keyword in expected_keywords_for_category(category) if keyword in haystack]


def looks_like_brand_locked(record: IntakeRecord) -> bool:
    name = record_product_name(record).lower()
    brand_terms = ["carhartt", "nike", "adidas", "stanley", "apple", "disney", "pokemon", "comfort colors"]
    return any(term in name for term in brand_terms)


def category_recommendation_label(score: int, reasons: list[str]) -> str:
    if score >= 85 and "brand/IP caution" not in reasons:
        return "A - priority sample and deep review"
    if score >= 72:
        return "B - watch and collect video/review evidence"
    return "C - keep as reference only"


def build_category_meeting_prompt(category: CategoryNode, record: IntakeRecord, score: int, reasons: list[str]) -> str:
    return (
        f"Discuss whether this product should be selected for {category.platform} / {category.category_path}. "
        f"Product: {record_product_name(record)}. Score: {score}. Evidence: {', '.join(reasons)}. "
        "Roles should review demand, content replicability, supply fit, listing opportunity, and IP risk."
    )


def record_product_name(record: IntakeRecord) -> str:
    return str(record.fields.get("product_name") or record.fields.get("page_title") or "").strip()


def record_url(record: IntakeRecord) -> str:
    return str(record.fields.get("url") or record.fields.get("page_url") or record.fields.get("product_url") or "").strip()


def record_product_key(record: IntakeRecord) -> str:
    fields = record.fields
    return str(fields.get("product_asin") or record_url(record) or record_product_name(record)).lower()


def is_new_release_record(record: IntakeRecord) -> bool:
    ranking_type = str(record.fields.get("ranking_type") or "").lower()
    return any(signal in ranking_type for signal in ["new release", "new releases", "new in", "new arrivals", "新品"])


def movement_key(record: IntakeRecord) -> str:
    fields = record.fields
    product_id = str(fields.get("product_asin") or fields.get("url") or fields.get("product_name") or "").strip().lower()
    if not product_id:
        return ""
    context = "|".join(
        [
            str(fields.get("marketplace") or fields.get("source_platform") or "").lower(),
            str(fields.get("ranking_type") or "").lower(),
            str(fields.get("category_path") or fields.get("ranking_page") or "").lower(),
            product_id,
        ]
    )
    return context


def parse_rank(value: Any) -> int | None:
    try:
        rank = int(float(value))
    except (TypeError, ValueError):
        return None
    return rank if rank > 0 else None


def build_selection_report(
    run_date: str,
    config: dict[str, Any],
    categories: list[CategoryNode],
    movements: list[dict[str, Any]],
    new_releases: list[dict[str, Any]],
    category_recommendations: list[dict[str, Any]],
    platform_rankings: dict[str, list[dict[str, Any]]] | None = None,
) -> str:
    threshold = int(config.get("monitoring", {}).get("sudden_growth_rank_improvement", 20) or 20)
    top_opportunities = sorted(
        category_recommendations,
        key=lambda item: (selection_platform_priority(str(item.get("platform") or "")), -int(item.get("score") or 0)),
    )[:8]
    lines = [
        f"# 选品情报简报 - {run_date}",
        "",
        "## Boss Summary",
        "",
        f"- 类目节点：{len(categories)}；排名变动：{len(movements)}；新品候选：{len(new_releases)}；类目候选：{len(category_recommendations)}。",
        "- TK / FastMoss / Kalodata 优先；Amazon 只作为补充，不替代 TikTok 视频和达人证据。",
        "- 品牌监控数据已从类目选品里隔离，避免同行品牌任务污染洗水T/洗面奶等精准商品报告。",
        "",
        "## Top Opportunities",
        "",
    ]
    if top_opportunities:
        for item in top_opportunities:
            lines.append(
                f"- {item.get('platform')} | 评分 {item.get('score')} | {item.get('product_name')} | "
                f"{item.get('category_path')} | {item.get('url')}"
            )
    else:
        lines.append("- 暂无可用候选。需要继续采集 TK 商品榜、视频、达人和评论。")
    lines.extend(["", "## Daily Platform Rankings", ""])
    platform_rankings = platform_rankings or build_platform_rankings(category_recommendations)
    if not platform_rankings:
        lines.append("- No platform ranking yet. Collect category-level data for each platform first.")
    for platform, items in platform_rankings.items():
        lines.append(f"### {platform}")
        for item in items[:10]:
            lines.append(
                f"{item.get('platform_rank')}. {item.get('strict_grade')} | score {item.get('score')} | "
                f"{item.get('product_name')} | rank {item.get('rank_position') or '-'} | {item.get('url')}"
            )
        lines.append("")
    lines.extend(
        [
            "",
            "<details>",
            "<summary>类目树和详细榜单</summary>",
            "",
            "## 类目树",
        ]
    )
    by_platform: dict[str, list[CategoryNode]] = {}
    for category in categories:
        by_platform.setdefault(category.platform, []).append(category)
    for platform, nodes in sorted(by_platform.items()):
        lines.append(f"### {platform}")
        for node in nodes:
            lines.append(f"- L{node.depth}: {node.category_path} | {', '.join(node.ranking_types) or '榜单'} | {node.url}")
        lines.append("")
    lines.extend(["## 突然增长监控", ""])
    sudden = [item for item in movements if item.get("rank_improvement", 0) >= threshold]
    if not sudden:
        lines.append("- 暂未发现突然增长商品。继续每日采集平台榜单快照。")
    for item in sudden[:30]:
        lines.append(
            f"- {item.get('product_name')} | {item.get('platform')} | {item.get('ranking_type')} | "
            f"排名 {item.get('previous_rank')} -> {item.get('latest_rank')} | 提升 {item.get('rank_improvement')} | {item.get('url')}"
        )
    lines.extend(["", "## 新品监控", ""])
    if not new_releases:
        lines.append("- 暂无新品候选。请为目标类目补充 New Releases / New In 链接并采集。")
    for item in new_releases[:30]:
        lines.append(
            f"- {item.get('product_name')} | {item.get('platform')} | {item.get('ranking_type')} | "
            f"排名 {item.get('rank_position') or '-'} | {item.get('url')}"
        )
    lines.extend(["", "## 按类目划分的最佳产品", ""])
    if not category_recommendations:
        lines.append("- 暂无类目级产品推荐。需要继续采集每个类目下的商品级榜单记录。")
    by_category: dict[str, list[dict[str, Any]]] = {}
    for item in category_recommendations:
        key = f"{item.get('platform')} | {item.get('category_path')}"
        by_category.setdefault(key, []).append(item)
    for category_key, items in sorted(by_category.items()):
        lines.append(f"### {category_key}")
        for item in items[:5]:
            lines.append(
                f"- {item.get('recommendation')} | 评分 {item.get('score')} | "
                f"{item.get('product_name')} | {item.get('ranking_type')} 排名 {item.get('rank_position') or '-'} | "
                f"{'; '.join(item.get('reasons') or [])} | {item.get('url')}"
            )
        lines.append("")
    lines.extend(["", "## 下一步采集规则", ""])
    lines.append("- 每个平台类目都要保存：类目路径、榜单URL、榜单类型、采集方式和验证状态。")
    lines.append("- 每条商品榜单记录都要保存：平台、类目路径、榜单类型、排名、商品链接、价格/评论/销量信号，以及可用截图。")
    lines.append("- 商品进入新品榜、进入 Top 30，或 24-72 小时内排名提升 20 名以上，就提升为高优先级候选。")
    lines.extend(["", "</details>"])
    return "\n".join(lines).rstrip() + "\n"


def selection_platform_priority(platform: str) -> int:
    text = platform.lower()
    if any(token in text for token in ["tiktok", "fastmoss", "kalodata"]):
        return 0
    if "amazon" in text:
        return 1
    return 2


def write_selection_report(root: Path, run_date: str, content: str) -> Path:
    path = root / "outputs" / f"{SELECTION_REPORT_PREFIX}_{run_date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_selection_json(
    root: Path,
    run_date: str,
    categories: list[CategoryNode],
    movements: list[dict[str, Any]],
    new_releases: list[dict[str, Any]],
    category_recommendations: list[dict[str, Any]],
    platform_rankings: dict[str, list[dict[str, Any]]] | None = None,
) -> Path:
    path = root / "outputs" / f"{SELECTION_REPORT_PREFIX}_{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_date": run_date,
        "categories": [
            {
                "platform": item.platform,
                "category_path": item.category_path,
                "depth": item.depth,
                "url": item.url,
                "ranking_types": item.ranking_types,
                "enabled": item.enabled,
            }
            for item in categories
        ],
        "movements": movements,
        "new_release_candidates": new_releases,
        "category_recommendations": category_recommendations,
        "platform_rankings": platform_rankings or build_platform_rankings(category_recommendations),
        "strict_scoring": {
            "grades": {"S": "90-100", "A": "82-89", "B": "70-81", "C": "55-69", "D": "0-54"},
            "rules": [
                "No product link cannot exceed 45.",
                "No rank and no sales/price evidence cannot exceed 54.",
                "No category match cannot exceed 72.",
                "No growth/new signal and rank outside top 10 cannot exceed 76.",
                "TikTok/FastMoss/Kalodata without video/creator/review/sales evidence cannot exceed 70.",
                "Brand/IP caution cannot exceed 69.",
                "Scores above 90 require at least five evidence dimensions.",
            ],
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def latest_selection_report(root: Path) -> tuple[str, Path | None]:
    output_dir = root / "outputs"
    paths = sorted(output_dir.glob(f"{SELECTION_REPORT_PREFIX}_*.md"), reverse=True)
    if not paths:
        return "还没有选品情报报告。", None
    path = paths[0]
    return path.read_text(encoding="utf-8"), path
