"""
Transaction Categorization Service
Auto-categorize transactions using ML
"""

from typing import Dict


class TransactionCategorizationService:
    """Transaction categorization"""
    
    def __init__(self):
        self.categories = {
            "groceries": ["supermarket", "grocery", "food"],
            "utilities": ["electricity", "water", "internet"],
            "entertainment": ["netflix", "spotify", "cinema"],
            "transport": ["uber", "bolt", "fuel"],
            "education": ["school", "tuition", "books"]
        }
    
    async def categorize_transaction(self, description: str, merchant: str) -> Dict:
        """Categorize transaction"""
        try:
            description_lower = description.lower()
            merchant_lower = merchant.lower()
            
            category = "other"
            confidence = 0.5
            
            for cat, keywords in self.categories.items():
                for keyword in keywords:
                    if keyword in description_lower or keyword in merchant_lower:
                        category = cat
                        confidence = 0.9
                        break
                if confidence > 0.8:
                    break
            
            return {
                "status": "success",
                "category": category,
                "confidence": confidence,
                "subcategory": None
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
