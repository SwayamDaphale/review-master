"""Structured requirement extraction service with LLM integration and deterministic fallback."""

import json
import logging
import re

from app.core.config import settings
from app.schemas.recommendation import (
    HardConstraint,
    ParsedRequirements,
    RequirementParseResponse,
    SoftPreference,
)
from app.services.llm.groq_provider import GroqProvider

logger = logging.getLogger("review_master.requirement_parser")

SUPPORTED_CATEGORIES = {"smartphone", "laptop", "external_ssd"}

CATEGORY_ALIASES = {
    "phone": "smartphone",
    "smartphone": "smartphone",
    "mobile": "smartphone",
    "cell": "smartphone",
    "laptop": "laptop",
    "notebook": "laptop",
    "macbook": "laptop",
    "computer": "laptop",
    "ssd": "external_ssd",
    "external ssd": "external_ssd",
    "portable ssd": "external_ssd",
    "drive": "external_ssd",
}

CATEGORY_SUPPORTED_ATTRIBUTES: dict[str, set[str]] = {
    "smartphone": {"ram", "storage", "battery_capacity", "display_size", "price", "camera", "5g"},
    "laptop": {"ram", "storage", "battery_life", "display_size", "processor", "price"},
    "external_ssd": {"capacity", "storage", "read_speed", "write_speed", "interface", "price"},
}


class RequirementParserService:
    """Service translating user natural language or structured input into validated ParsedRequirements."""

    PARSER_VERSION = "v1"

    def __init__(self, llm_provider: GroqProvider | None = None):
        self.llm_provider: GroqProvider | None = None
        if llm_provider is not None:
            self.llm_provider = llm_provider
        elif settings.GROQ_API_KEY:
            try:
                self.llm_provider = GroqProvider(
                    api_key=settings.GROQ_API_KEY,
                    model=settings.GROQ_MODEL,
                )
            except Exception:  # noqa: BLE001
                self.llm_provider = None

    def parse_query(
        self,
        query: str,
        category_hint: str | None = None,
        use_llm: bool = True,
    ) -> RequirementParseResponse:
        """Parse natural language query into typed validated requirements."""
        cleaned_query = query.strip()

        parsed: ParsedRequirements | None = None
        if use_llm:
            try:
                parsed = self._parse_with_llm(cleaned_query, category_hint)
            except Exception as exc:  # noqa: BLE001
                logger.info("LLM requirement parsing failed or unavailable (%s), using deterministic parser", exc)
                parsed = None

        if not parsed:
            parsed = self.parse_deterministic(cleaned_query, category_hint)

        # Post-validation against supported catalog attributes
        supported_attrs = CATEGORY_SUPPORTED_ATTRIBUTES.get(parsed.category_key, set())
        valid_constraints: list[HardConstraint] = []
        unsupported: list[str] = []

        for hc in parsed.hard_constraints:
            key_norm = hc.attribute_key.lower().strip()
            # Canonical normalization aliases
            if key_norm in ("memory", "system memory"):
                key_norm = "ram"
            elif key_norm in ("rom", "disk", "ssd", "internal storage"):
                key_norm = "storage" if parsed.category_key != "external_ssd" else "capacity"
            elif key_norm in ("battery", "mah"):
                key_norm = "battery_capacity"

            if key_norm in supported_attrs:
                hc.attribute_key = key_norm
                valid_constraints.append(hc)
            else:
                unsupported.append(hc.attribute_key)

        parsed.hard_constraints = valid_constraints

        clarifications = []
        if unsupported:
            clarifications.append(
                f"The following requested attributes are not supported in category '{parsed.category_key}': {', '.join(unsupported)}."
            )
        if parsed.ambiguities:
            clarifications.extend(parsed.ambiguities)

        return RequirementParseResponse(
            requirements=parsed,
            clarifications_needed=clarifications,
            unsupported_attributes=unsupported,
        )

    def parse_deterministic(
        self,
        query: str,
        category_hint: str | None = None,
    ) -> ParsedRequirements:
        """Pure deterministic regex-based requirement parser."""
        q_lower = query.lower()

        # 1. Detect Category
        detected_category = "smartphone"
        if category_hint and category_hint.lower() in SUPPORTED_CATEGORIES:
            detected_category = category_hint.lower()
        else:
            for alias, cat in CATEGORY_ALIASES.items():
                if re.search(r"\b" + re.escape(alias) + r"\b", q_lower):
                    detected_category = cat
                    break

        hard_constraints: list[HardConstraint] = []
        soft_preferences: list[SoftPreference] = []
        excluded_brands: list[str] = []
        ambiguities: list[str] = []

        # 2. Extract Budget (e.g., under 80000, under ₹25,000, 70k, 1.5 lakh)
        budget_max: float | None = None
        budget_match = re.search(
            r"(?:under|below|less than|budget of|within|upto|up to)?\s*(?:₹|rs\.?|inr)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(k|thousand|lakh)?\b",
            q_lower,
        )
        if budget_match:
            raw_num_str = budget_match.group(1).replace(",", "")
            try:
                base_val = float(raw_num_str)
                multiplier_str = budget_match.group(2)
                if multiplier_str in ("k", "thousand"):
                    base_val *= 1000
                elif multiplier_str == "lakh":
                    base_val *= 100000

                # Validate reasonable consumer price threshold
                if base_val >= 500:
                    budget_max = base_val
            except ValueError:
                pass

        # 3. Extract RAM (e.g., 8gb ram, 16 gb ram, at least 16gb)
        ram_match = re.search(r"(\d+)\s*(?:gb|gigabytes?)\s*(?:of\s*)?ram", q_lower)
        if not ram_match:
            ram_match = re.search(r"ram\s*(?:of|at least|>=|:)?\s*(\d+)\s*(?:gb)?", q_lower)
        if ram_match:
            try:
                ram_val = int(ram_match.group(1))
                hard_constraints.append(
                    HardConstraint(
                        attribute_key="ram",
                        operator=">=",
                        target_value=ram_val,
                        unit="GB",
                        description=f"At least {ram_val} GB RAM",
                    )
                )
            except ValueError:
                pass

        # 4. Extract Storage / Capacity (e.g., 128gb storage, 1 tb ssd, 512gb)
        storage_match = re.search(r"(\d+)\s*(tb|gb)\s*(?:of\s*)?(?:ssd|storage|rom|internal|drive|capacity)", q_lower)
        if not storage_match:
            storage_match = re.search(r"(?:ssd|storage|rom|internal|drive|capacity)\s*(?:of|at least|>=|:)?\s*(\d+)\s*(tb|gb)", q_lower)
            if storage_match:
                s_val = int(storage_match.group(1))
                s_unit = storage_match.group(2).upper()
            else:
                s_val, s_unit = None, None
        else:
            s_val = int(storage_match.group(1))
            s_unit = storage_match.group(2).upper()

        if s_val is not None and s_unit is not None:
            target_gb = s_val * 1000 if s_unit == "TB" else s_val
            attr_name = "capacity" if detected_category == "external_ssd" else "storage"
            hard_constraints.append(
                HardConstraint(
                    attribute_key=attr_name,
                    operator=">=",
                    target_value=target_gb,
                    unit="GB",
                    description=f"At least {target_gb} GB storage",
                )
            )

        # 5. Extract Soft Preferences
        if "battery" in q_lower:
            soft_preferences.append(
                SoftPreference(
                    preference_key="battery",
                    preferred_direction="higher",
                    description="Good battery life preferred",
                )
            )
        if "camera" in q_lower:
            soft_preferences.append(
                SoftPreference(
                    preference_key="camera",
                    preferred_direction="higher",
                    description="High quality camera preferred",
                )
            )
        if "lightweight" in q_lower or "portable" in q_lower:
            soft_preferences.append(
                SoftPreference(
                    preference_key="weight",
                    preferred_direction="lower",
                    description="Lightweight and portable preferred",
                )
            )

        # 6. Excluded brands
        for brand in ["samsung", "apple", "xiaomi", "dell", "hp", "lenovo", "sandisk", "kingston"]:
            if re.search(r"(?:not|no|exclude|without)\s+" + brand, q_lower):
                excluded_brands.append(brand.title())

        return ParsedRequirements(
            raw_query=query,
            category_key=detected_category,
            budget_max=budget_max,
            budget_currency="INR",
            hard_constraints=hard_constraints,
            soft_preferences=soft_preferences,
            required_attributes=[hc.attribute_key for hc in hard_constraints],
            excluded_brands=excluded_brands,
            ambiguities=ambiguities,
            extraction_confidence=0.9,
            parser_version=self.PARSER_VERSION,
            extraction_source="deterministic_fallback",
        )

    def _parse_with_llm(
        self,
        query: str,
        category_hint: str | None,
    ) -> ParsedRequirements | None:
        """Call Groq provider with structured JSON schema prompt."""
        if not self.llm_provider:
            return None
        prompt = (
            "You are a strict product requirement extraction assistant. "
            "Extract structured purchasing constraints from the user request into valid JSON.\n"
            "Format:\n"
            "{\n"
            '  "category_key": "smartphone" | "laptop" | "external_ssd",\n'
            '  "budget_max": number | null,\n'
            '  "budget_currency": "INR",\n'
            '  "hard_constraints": [\n'
            '    {"attribute_key": "ram", "operator": ">=", "target_value": 8, "unit": "GB", "description": "At least 8GB RAM"}\n'
            "  ],\n"
            '  "soft_preferences": [\n'
            '    {"preference_key": "battery", "preferred_direction": "higher", "description": "Good battery"}\n'
            "  ],\n"
            '  "excluded_brands": ["BrandA"],\n'
            '  "ambiguities": []\n'
            "}\n"
            f"Category hint: {category_hint or 'none'}\n"
            f"User query: {query}\n"
            "Respond ONLY with valid JSON."
        )

        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                res = pool.submit(asyncio.run, self.llm_provider.generate_text(prompt=prompt)).result()
        else:
            res = loop.run_until_complete(self.llm_provider.generate_text(prompt=prompt))

        response_text = res.text if res else None
        if not response_text:
            return None

        # Clean JSON from markdown code fences if present
        clean_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", response_text.strip(), flags=re.MULTILINE)
        data = json.loads(clean_json)

        # Validate with Pydantic
        req = ParsedRequirements.model_validate(data)
        req.raw_query = query
        req.extraction_source = "llm"
        req.parser_version = self.PARSER_VERSION
        return req
