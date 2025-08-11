"""
LinkedIn Search Parameters Helper

This module provides a helper class to build correct LinkedIn search parameters
that match Unipile's API structure. It makes it easy to create complex searches
like "sales directors in technology companies with more than 50 employees but 
less than 1000 within Sweden".

Usage:
    helper = SearchParametersHelper()
    
    # Build a search for sales directors in tech companies in Sweden
    search_config = helper.build_search(
        api="sales_navigator",
        category="people",
        keywords="sales director",
        location_ids=[102277331],  # Sweden location ID
        company_headcount_min=51,
        company_headcount_max=1000,
        industry_ids=["4"],  # Technology industry ID
        seniority_min=5
    )
"""

from typing import List, Dict, Any, Optional, Union


class SearchParametersHelper:
    """
    Helper class to build LinkedIn search parameters that match Unipile's API structure.
    """
    
    def __init__(self):
        # Common location IDs (you can get these via get_search_parameters)
        self.COMMON_LOCATIONS = {
            "sweden": "102277331",
            "stockholm": "102277331", 
            "gothenburg": "102277331",
            "malmo": "102277331",
            "united_states": "101174742",
            "california": "102277331",
            "san_francisco": "102277331",
            "new_york": "102277331",
            "london": "102277331",
            "uk": "101165590",
            "germany": "101282230",
            "berlin": "101282230",
            "munich": "101282230"
        }
        
        # Common industry IDs
        self.COMMON_INDUSTRIES = {
            "technology": "4",
            "software_development": "4", 
            "information_technology": "6",
            "consulting": "6",
            "financial_services": "43",
            "healthcare": "5",
            "education": "2",
            "manufacturing": "3",
            "retail": "7",
            "marketing": "9"
        }
        
        # Common seniority levels
        self.SENIORITY_LEVELS = {
            "entry": {"min": 0, "max": 2},
            "mid": {"min": 3, "max": 7},
            "senior": {"min": 5, "max": 10},
            "director": {"min": 8, "max": 15},
            "executive": {"min": 10, "max": 20},
            "cxo": {"min": 15, "max": 30}
        }
    
    def build_search(
        self,
        api: str = "sales_navigator",
        category: str = "people",
        keywords: Optional[str] = None,
        location_ids: Optional[List[str]] = None,
        location_names: Optional[List[str]] = None,
        company_headcount_min: Optional[int] = None,
        company_headcount_max: Optional[int] = None,
        industry_ids: Optional[List[str]] = None,
        industry_names: Optional[List[str]] = None,
        seniority_min: Optional[int] = None,
        seniority_max: Optional[int] = None,
        seniority_level: Optional[str] = None,
        profile_language: Optional[List[str]] = None,
        network_distance: Optional[List[int]] = None,
        has_posted: Optional[bool] = None,
        tenure_min: Optional[int] = None,
        tenure_max: Optional[int] = None,
        skills: Optional[List[Dict[str, Any]]] = None,
        role_keywords: Optional[str] = None,
        role_priority: str = "MUST_HAVE",
        role_scope: str = "CURRENT_OR_PAST"
    ) -> Dict[str, Any]:
        """
        Build a LinkedIn search configuration that matches Unipile's API structure.
        
        Args:
            api: "sales_navigator", "classic", or "recruiter"
            category: "people", "companies", "jobs", or "posts"
            keywords: Search keywords
            location_ids: List of location IDs from get_search_parameters
            location_names: List of location names (will be converted to IDs)
            company_headcount_min: Minimum company size
            company_headcount_max: Maximum company size
            industry_ids: List of industry IDs
            industry_names: List of industry names (will be converted to IDs)
            seniority_min: Minimum years of experience
            seniority_max: Maximum years of experience
            seniority_level: Predefined level ("entry", "mid", "senior", "director", "executive", "cxo")
            profile_language: List of language codes (e.g., ["en", "sv"])
            network_distance: List of connection degrees (e.g., [1, 2, 3])
            has_posted: Whether they have posted on LinkedIn
            tenure_min: Minimum tenure at current company
            tenure_max: Maximum tenure at current company
            skills: List of skill objects with id and priority
            role_keywords: Role/title keywords
            role_priority: "MUST_HAVE", "NICE_TO_HAVE", "DOESNT_HAVE"
            role_scope: "CURRENT_OR_PAST", "CURRENT", "PAST"
            
        Returns:
            Dict containing the search configuration
        """
        search_config = {
            "api": api,
            "category": category
        }
        
        # Add keywords if provided
        if keywords:
            search_config["keywords"] = keywords
        
        # Handle locations
        if location_ids or location_names:
            locations = []
            if location_ids:
                locations.extend(location_ids)
            if location_names:
                for name in location_names:
                    location_id = self.COMMON_LOCATIONS.get(name.lower())
                    if location_id:
                        locations.append(location_id)
            if locations:
                # For Sales Navigator, location should be an object with include/exclude
                search_config["location"] = {"include": locations}
        
        # Handle company headcount
        if company_headcount_min is not None or company_headcount_max is not None:
            headcount_config = {}
            if company_headcount_min is not None:
                headcount_config["min"] = company_headcount_min
            if company_headcount_max is not None:
                headcount_config["max"] = company_headcount_max
            search_config["company_headcount"] = [headcount_config]
        
        # Handle industries
        if industry_ids or industry_names:
            industries = []
            if industry_ids:
                industries.extend(industry_ids)
            if industry_names:
                for name in industry_names:
                    industry_id = self.COMMON_INDUSTRIES.get(name.lower())
                    if industry_id:
                        industries.append(industry_id)
            if industries:
                search_config["industry"] = {"include": industries}
        
        # Handle seniority
        if seniority_level:
            if seniority_level in self.SENIORITY_LEVELS:
                level_config = self.SENIORITY_LEVELS[seniority_level]
                # For Sales Navigator, seniority should be an object with include/exclude
                search_config["seniority"] = {"include": ["director", "experienced_manager"]}
        elif seniority_min is not None or seniority_max is not None:
            # For numeric seniority, use the array format
            seniority_config = {}
            if seniority_min is not None:
                seniority_config["min"] = seniority_min
            if seniority_max is not None:
                seniority_config["max"] = seniority_max
            search_config["seniority"] = [seniority_config]
        
        # Handle profile language
        if profile_language:
            search_config["profile_language"] = profile_language
        
        # Handle network distance
        if network_distance:
            search_config["network_distance"] = network_distance
        
        # Handle has posted
        if has_posted is not None:
            search_config["has_posted"] = has_posted
        
        # Handle tenure
        if tenure_min is not None or tenure_max is not None:
            tenure_config = {}
            if tenure_min is not None:
                tenure_config["min"] = tenure_min
            if tenure_max is not None:
                tenure_config["max"] = tenure_max
            search_config["tenure"] = [tenure_config]
        
        # Handle skills
        if skills:
            search_config["skills"] = skills
        
        # Handle role
        if role_keywords:
            search_config["role"] = [{
                "keywords": role_keywords,
                "priority": role_priority,
                "scope": role_scope
            }]
        
        return search_config
    
    def get_location_id(self, location_name: str) -> Optional[str]:
        """Get location ID for a common location name."""
        return self.COMMON_LOCATIONS.get(location_name.lower())
    
    def get_industry_id(self, industry_name: str) -> Optional[str]:
        """Get industry ID for a common industry name."""
        return self.COMMON_INDUSTRIES.get(industry_name.lower())
    
    def get_seniority_config(self, level: str) -> Optional[Dict[str, int]]:
        """Get seniority configuration for a predefined level."""
        return self.SENIORITY_LEVELS.get(level)
    
    def build_skill_config(self, skill_id: str, priority: str = "MUST_HAVE") -> Dict[str, str]:
        """Build a skill configuration object."""
        return {
            "id": skill_id,
            "priority": priority  # "MUST_HAVE", "NICE_TO_HAVE", "DOESNT_HAVE"
        }


# Convenience functions for common search patterns
def build_sales_director_search(
    location_name: str = "sweden",
    company_size_min: int = 51,
    company_size_max: int = 1000,
    industry_name: str = "technology"
) -> Dict[str, Any]:
    """
    Build a search for sales directors in technology companies.
    
    Example:
        search_config = build_sales_director_search(
            location_name="sweden",
            company_size_min=51,
            company_size_max=1000,
            industry_name="technology"
        )
    """
    helper = SearchParametersHelper()
    
    return helper.build_search(
        api="sales_navigator",
        category="people",
        keywords="sales director",
        location_names=[location_name],
        company_headcount_min=company_size_min,
        company_headcount_max=company_size_max,
        industry_names=[industry_name],
        seniority_level="senior"
    )


def build_tech_engineer_search(
    location_name: str = "sweden",
    company_size_min: int = 51,
    company_size_max: int = 1000,
    seniority_level: str = "senior"
) -> Dict[str, Any]:
    """
    Build a search for software engineers in tech companies.
    """
    helper = SearchParametersHelper()
    
    return helper.build_search(
        api="sales_navigator",
        category="people",
        keywords="software engineer",
        location_names=[location_name],
        company_headcount_min=company_size_min,
        company_headcount_max=company_size_max,
        industry_names=["technology"],
        seniority_level=seniority_level
    )


def build_cxo_search(
    location_name: str = "sweden",
    company_size_min: int = 51,
    company_size_max: int = 1000
) -> Dict[str, Any]:
    """
    Build a search for C-level executives.
    """
    helper = SearchParametersHelper()
    
    return helper.build_search(
        api="sales_navigator",
        category="people",
        keywords="CEO OR CTO OR CFO OR COO",
        location_names=[location_name],
        company_headcount_min=company_size_min,
        company_headcount_max=company_size_max,
        seniority_level="cxo"
    )
