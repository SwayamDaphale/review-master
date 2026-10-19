export const smartphoneFixtures = [
  {
    id: "fixture_01_galaxy_s24",
    description: "Samsung Galaxy S24 5G (8GB RAM, 128GB Storage) - Complete standard listing",
    url: "https://www.amazon.in/Samsung-Galaxy-Storage-Graphite-SM-S921BZKDINS/dp/B0CS571XMS",
    title: "Samsung Galaxy S24 5G (Onyx Black, 8GB RAM, 128GB Storage)",
    elements: {
      "#productTitle": "Samsung Galaxy S24 5G (Onyx Black, 8GB RAM, 128GB Storage)",
      "#bylineInfo": "Brand: Samsung",
      ".a-price .a-offscreen": "₹74,999",
      "#acrPopover[title]": "4.4 out of 5 stars",
      "#acrCustomerReviewText": "1,248 ratings",
      "#availability span": "In stock."
    },
    specs: [
      { label: "Brand", value: "Samsung" },
      { label: "Model Name", value: "Galaxy S24" },
      { label: "Item model number", value: "SM-S921BZKDINS" },
      { label: "RAM", value: "8 GB" },
      { label: "Memory Storage Capacity", value: "128 GB" },
      { label: "Screen Size", value: "6.2 Inches" },
      { label: "Battery Capacity", value: "4000 mAh" },
      { label: "Operating System", value: "Android 14.0" },
      { label: "Cellular Technology", value: "5G" }
    ],
    expected: {
      brand: "Samsung",
      model_name: "Galaxy S24",
      ram_gb: 8,
      storage_gb: 128,
      price_amount: 74999,
      status: "valid",
      identity_status: "identified"
    }
  },
  {
    id: "fixture_02_galaxy_s24_variant_256gb",
    description: "Samsung Galaxy S24 5G (8GB RAM, 256GB Storage) - Same model, distinct variant",
    url: "https://www.amazon.in/Samsung-Galaxy-Storage-Graphite-SM-S921BZKDINS/dp/B0CS572YNT",
    title: "Samsung Galaxy S24 5G (Cobalt Violet, 8GB RAM, 256GB Storage)",
    elements: {
      "#productTitle": "Samsung Galaxy S24 5G (Cobalt Violet, 8GB RAM, 256GB Storage)",
      "#bylineInfo": "Brand: Samsung",
      ".a-price .a-offscreen": "₹79,999",
      "#acrPopover[title]": "4.4 out of 5 stars",
      "#acrCustomerReviewText": "1,248 ratings",
      "#availability span": "In stock."
    },
    specs: [
      { label: "Brand", value: "Samsung" },
      { label: "Model Name", value: "Galaxy S24" },
      { label: "RAM", value: "8 GB" },
      { label: "Memory Storage Capacity", value: "256 GB" },
      { label: "Screen Size", value: "6.2 Inches" },
      { label: "Battery Capacity", value: "4000 mAh" },
      { label: "Operating System", value: "Android 14.0" }
    ],
    expected: {
      ram_gb: 8,
      storage_gb: 256,
      price_amount: 79999,
      status: "valid",
      identity_status: "identified"
    }
  },
  {
    id: "fixture_03_iphone_15",
    description: "Apple iPhone 15 (128 GB) - Blue with iOS and cm-based display spec",
    url: "https://www.amazon.in/Apple-iPhone-15-128-GB/dp/B0CHX1W1XY",
    title: "Apple iPhone 15 (128 GB) - Blue",
    elements: {
      "#productTitle": "Apple iPhone 15 (128 GB) - Blue",
      "#bylineInfo": "Visit the Apple Store",
      ".a-price .a-offscreen": "₹70,999.00",
      "#acrPopover[title]": "4.6 out of 5 stars",
      "#acrCustomerReviewText": "5,312 ratings",
      "#availability span": "In stock."
    },
    specs: [
      { label: "Brand", value: "Apple" },
      { label: "Model Name", value: "iPhone 15" },
      { label: "Item model number", value: "MTP43HN/A" },
      { label: "Memory Storage Capacity", value: "128 GB" },
      { label: "Standing screen display size", value: "15.54 cm" },
      { label: "Operating System", value: "iOS" },
      { label: "Cellular Technology", value: "5G" }
    ],
    expected: {
      brand: "Apple",
      model_name: "iPhone 15",
      storage_gb: 128,
      ram_gb: null, // iPhones don't list RAM on Amazon; must stay null!
      price_amount: 70999,
      status: "needs_review", // because RAM is null
      identity_status: "probable"
    }
  },
  {
    id: "fixture_04_oneplus_12r",
    description: "OnePlus 12R (Cool Blue, 16GB RAM, 256GB Storage) - 5500 mAh battery",
    url: "https://www.amazon.in/OnePlus-Cool-Blue-256GB-Storage/dp/B0CQPN4QCW",
    title: "OnePlus 12R (Cool Blue, 16GB RAM, 256GB Storage)",
    elements: {
      "#productTitle": "OnePlus 12R (Cool Blue, 16GB RAM, 256GB Storage)",
      "#bylineInfo": "Brand: OnePlus",
      ".a-price .a-offscreen": "₹45,999",
      "#acrPopover[title]": "4.3 out of 5 stars",
      "#acrCustomerReviewText": "2,190 ratings",
      "#availability span": "In stock."
    },
    specs: [
      { label: "Brand", value: "OnePlus" },
      { label: "Model Name", value: "OnePlus 12R" },
      { label: "RAM", value: "16 GB" },
      { label: "Internal Storage", value: "256 GB" },
      { label: "Screen Size", value: "6.78 Inches" },
      { label: "Battery Power Rating", value: "5500 mAh" },
      { label: "Operating System", value: "OxygenOS based on Android 14" }
    ],
    expected: {
      brand: "OnePlus",
      model_name: "OnePlus 12R",
      ram_gb: 16,
      storage_gb: 256,
      battery_capacity_mah: 5500,
      price_amount: 45999,
      status: "valid"
    }
  },
  {
    id: "fixture_05_redmi_13c_4g",
    description: "Redmi 13C (Starshine Green, 4GB RAM, 128GB Storage) - 4G only smartphone",
    url: "https://www.amazon.in/Redmi-Starshine-Green-128GB-Storage/dp/B0CNX6W7N1",
    title: "Redmi 13C (Starshine Green, 4GB RAM, 128GB Storage) | Powered by 4G MediaTek Helio G85",
    elements: {
      "#productTitle": "Redmi 13C (Starshine Green, 4GB RAM, 128GB Storage) | Powered by 4G MediaTek Helio G85",
      "#bylineInfo": "Brand: Redmi",
      ".a-price .a-offscreen": "₹7,699",
      "#acrPopover[title]": "4.1 out of 5 stars",
      "#acrCustomerReviewText": "8,401 ratings",
      "#availability span": "In stock."
    },
    specs: [
      { label: "Brand", value: "Redmi" },
      { label: "Model Name", value: "Redmi 13C" },
      { label: "RAM", value: "4 GB" },
      { label: "Memory Storage Capacity", value: "128 GB" },
      { label: "Screen Size", value: "6.74 Inches" },
      { label: "Battery Capacity", value: "5000 mAh" },
      { label: "Cellular Technology", value: "4G LTE" }
    ],
    expected: {
      supports_5g: false,
      ram_gb: 4,
      storage_gb: 128,
      price_amount: 7699,
      status: "valid"
    }
  },
  {
    id: "fixture_06_missing_price_out_of_stock",
    description: "Out of stock item where price is unavailable - price must remain null (not 0)",
    url: "https://www.amazon.in/dp/B08L5VJZ88",
    title: "Google Pixel 7 (Snow, 8GB RAM, 128GB Storage)",
    elements: {
      "#productTitle": "Google Pixel 7 (Snow, 8GB RAM, 128GB Storage)",
      "#bylineInfo": "Brand: Google",
      "#availability span": "Currently unavailable."
    },
    specs: [
      { label: "Brand", value: "Google" },
      { label: "Model Name", value: "Pixel 7" },
      { label: "RAM", value: "8 GB" },
      { label: "Storage", value: "128 GB" }
    ],
    expected: {
      price_amount: null,
      currency: null,
      availability: "out_of_stock",
      status: "needs_review"
    }
  },
  {
    id: "fixture_07_ambiguous_model",
    description: "Ambiguous listing missing clear model name or number",
    url: "https://www.amazon.in/dp/B09ABCDEFG",
    title: "Premium Android Smartphone with High Resolution Camera",
    elements: {
      "#productTitle": "Premium Android Smartphone with High Resolution Camera",
      ".a-price .a-offscreen": "₹12,499"
    },
    specs: [
      { label: "RAM", value: "6 GB" },
      { label: "Storage", value: "128 GB" }
    ],
    expected: {
      brand: null,
      model_name: null,
      identity_status: "ambiguous",
      status: "needs_review"
    }
  },
  {
    id: "fixture_08_missing_ram_storage_in_specs_fallback_title",
    description: "RAM and storage absent from spec table but present in product title",
    url: "https://www.amazon.in/dp/B08XYZ1234",
    title: "iQOO Z9x 5G (Tornado Green, 6GB RAM, 128GB Storage)",
    elements: {
      "#productTitle": "iQOO Z9x 5G (Tornado Green, 6GB RAM, 128GB Storage)",
      "#bylineInfo": "Brand: iQOO",
      ".a-price .a-offscreen": "₹12,999"
    },
    specs: [
      { label: "Brand", value: "iQOO" },
      { label: "Model Name", value: "Z9x 5G" },
      { label: "Battery Capacity", value: "6000 mAh" }
    ],
    expected: {
      brand: "iQOO",
      model_name: "Z9x 5G",
      ram_gb: 6,
      storage_gb: 128,
      battery_capacity_mah: 6000,
      price_amount: 12999
    }
  },
  {
    id: "fixture_09_tb_storage_flagship",
    description: "Ultra flagship smartphone with 1TB storage - verifies TB to GB conversion",
    url: "https://www.amazon.in/dp/B0CHX1W111",
    title: "Apple iPhone 15 Pro Max (1 TB) - Natural Titanium",
    elements: {
      "#productTitle": "Apple iPhone 15 Pro Max (1 TB) - Natural Titanium",
      "#bylineInfo": "Visit the Apple Store",
      ".a-price .a-offscreen": "₹1,99,900"
    },
    specs: [
      { label: "Brand", value: "Apple" },
      { label: "Model Name", value: "iPhone 15 Pro Max" },
      { label: "Memory Storage Capacity", value: "1 TB" }
    ],
    expected: {
      brand: "Apple",
      model_name: "iPhone 15 Pro Max",
      storage_gb: 1024,
      price_amount: 199900
    }
  },
  {
    id: "fixture_10_invalid_empty_page",
    description: "Non-product page or 404 missing product title",
    url: "https://www.amazon.in/dp/B000000000",
    title: "",
    elements: {},
    specs: [],
    expected: {
      status: "invalid"
    }
  },
  {
    id: "fixture_11_redmi_turbo_5_ram_memory_spec",
    description: "Redmi Turbo 5 with RAM Memory - 8 GB in table and 8GB + 256GB in title",
    url: "https://www.amazon.in/dp/B0H297XH3K",
    title: "REDMI Turbo 5 (8GB + 256GB) Asphalt Black | Dimensity 8500 Ultra | Mega 7540mAh Battery",
    elements: {
      "#productTitle": "REDMI Turbo 5 (8GB + 256GB) Asphalt Black | Dimensity 8500 Ultra | Mega 7540mAh Battery",
      "#bylineInfo": "Brand: Redmi",
      ".a-price .a-offscreen": "₹40,999",
      "#acrPopover[title]": "4.1 out of 5 stars",
      "#acrCustomerReviewText": "811 ratings",
      "#variation_size_name .selection": "8GB+256GB",
      "#availability span": "In stock."
    },
    specs: [
      { label: "Brand", value: "Redmi" },
      { label: "Operating System", value: "HyperOS" },
      { label: "RAM Memory Installed Size", value: "8 GB" },
      { label: "CPU Speed", value: "3.4 GHz" },
      { label: "Memory Storage Capacity", value: "256 GB" },
      { label: "Battery Capacity", value: "7540 mAh" },
      { label: "Cellular Technology", value: "5G" }
    ],
    expected: {
      brand: "Redmi",
      model_name: "Turbo 5",
      ram_gb: 8,
      storage_gb: 256,
      battery_capacity_mah: 7540,
      price_amount: 40999,
      status: "needs_review",
      identity_status: "identified"
    }
  },
  {
    id: "fixture_12_paired_title_fallback_slash",
    description: "Unambiguous 12GB/256GB title fallback when specs table omits RAM",
    url: "https://www.amazon.in/dp/B09REALME1",
    title: "Realme GT 6T 5G (Razor Green, 12GB/256GB)",
    elements: {
      "#productTitle": "Realme GT 6T 5G (Razor Green, 12GB/256GB)",
      "#bylineInfo": "Brand: Realme",
      ".a-price .a-offscreen": "₹32,999"
    },
    specs: [
      { label: "Brand", value: "Realme" },
      { label: "Model Name", value: "GT 6T" }
    ],
    expected: {
      brand: "Realme",
      model_name: "GT 6T",
      ram_gb: 12,
      storage_gb: 256,
      price_amount: 32999
    }
  }
];
