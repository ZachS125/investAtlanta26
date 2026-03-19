import pandas as pd

# 1. Load the Excel file into a pandas DataFrame
# Note: If your file has multiple sheets, you can specify sheet_name='Sheet1'
df = pd.read_excel(r'D:\LZY\Projects\investAtlanta26\Organize\Atlanta_Business_License_Records_2025.xlsx')

# 2. Export the DataFrame to a CSV file
# index=False prevents pandas from writing row numbers into the CSV
df.to_csv('Atlanta_Business_License_Records_2025.csv', index=False)

print("Conversion complete!")

import pandas as pd
import re

# 1. Load and Clean
df = pd.read_csv('Atlanta_Business_License_Records_2025.csv')

# Create a combined, cleaned search string from both Name and DBA columns
df['company_name_clean'] = df['company_name'].fillna('').str.lower()
df['company_dba_clean'] = df['company_dba'].fillna('').str.lower()
df['search_name'] = df['company_name_clean'] + " " + df['company_dba_clean']

# Ensure NAICS codes are numeric for filtering
df['naics_code'] = pd.to_numeric(df['naics_code'], errors='coerce').fillna(0)

# ==========================================
# TIER 1: THE "GOLDEN TICKET" BRAND OVERRIDE
# ==========================================
# These chains guarantee high-volume fresh food access (>3 items). 
# If a string matches these, we keep them immediately regardless of NAICS.
major_chains_pattern = re.compile(
    r'\b(publix|kroger|walmart|target|whole foods|aldi|lidl|trader joe|'
    r'sprouts|h mart|hmart|wayfield|nam dae mun|buford highway farmers market|'
    r'city farmers market|sav-a-lot|save a lot|food giant|piggly wiggly|'
    r'fresh market|seafood city|super h mart)\b'
)

# Apply mask and route to "Keep"
is_major_chain = df['search_name'].str.contains(major_chains_pattern)
df_chain_keep = df[is_major_chain].copy()

# Remove the found chains from the pool so we don't process them again
df_remaining = df[~is_major_chain].copy()


# ==========================================
# TIER 2: EXPANDED NAICS FILTERING
# ==========================================
# Definite keeps (Supermarkets, Fruit/Veg)
keep_naics = [445110, 445230] 

# Expanded 'Maybe' Pool to catch big-box stores and Latino markets 
maybe_naics = [
    445120, # Convenience Stores
    445299, # All Other Specialty Food Stores
    452311, # Warehouse Clubs and Supercenters (Walmart/Target catch-all)
    452210, # Department Stores (Sometimes Target)
    452319, # All Other Gen Merchandise (Dollar Tree, Dollar General)
    445210  # Meat Markets (Latino Carnicerias often have full produce aisles)
]

df_naics_keep = df_remaining[df_remaining['naics_code'].isin(keep_naics)].copy()
df_maybe = df_remaining[df_remaining['naics_code'].isin(maybe_naics)].copy()

# Everything else defaults to discard (Restaurants, Construction, Tech, etc.)
df_discard_base = df_remaining[~df_remaining['naics_code'].isin(keep_naics + maybe_naics)].copy()


# ==========================================
# TIER 3: REGEX NLP ON THE "MAYBE" POOL
# ==========================================
# Heavy demoters: Catch things that are legally "Specialty/Convenience" but sell no fresh food.
exclude_pattern = re.compile(
    r'\b(vape|smoke|tobacco|cigar|liquor|wine|beer|beverage|bakery|pastry|'
    r'dessert|sweet|cake|candy|boba|tea|coffee|donut|doughnut|deli|cell|'
    r'wireless|tire|auto|boutique|apparel|hair|nails|spa|beauty|dollar)\b' 
)
# Note on "dollar": Most standard Dollar Trees do not carry >3 fresh produce items. 
# If your team wants to manually check every Family Dollar, remove "dollar" from this list.

# Promoters: Catch ambiguous codes that sound like full grocers
include_pattern = re.compile(
    r'\b(produce|supermercado|mercado|grocery|groceries|farmer|carniceria)\b'
)

# Apply masks to 'Maybe' pool
is_excluded = df_maybe['search_name'].str.contains(exclude_pattern)
is_included = df_maybe['search_name'].str.contains(include_pattern)

# Route the 'Maybes'
df_maybe_to_discard = df_maybe[is_excluded].copy()
df_maybe_to_keep = df_maybe[is_included & ~is_excluded].copy()

# The remaining "Maybes" (e.g., generic "Corner Store LLC")
df_requires_review = df_maybe[~is_excluded & ~is_included].copy()


# ==========================================
# TIER 4: RECOMBINE AND EXPORT
# ==========================================
# Combine all 'Keeps' and remove any accidental duplicates
df_final_keep = pd.concat([df_chain_keep, df_naics_keep, df_maybe_to_keep]).drop_duplicates(subset=['license_number'])

# Combine all 'Discards'
df_final_discard = pd.concat([df_discard_base, df_maybe_to_discard]).drop_duplicates(subset=['license_number'])

# Export for your team (Guarantees it saves to your specific project folder)
df_final_keep.to_csv(r'D:\LZY\Projects\investAtlanta26\Organize\high_confidence_fresh_food.csv', index=False)
df_requires_review.to_csv(r'D:\LZY\Projects\investAtlanta26\Organize\manual_audit_required.csv', index=False)

# Optional: Add this line if you ALSO want to save the list of businesses that were filtered out/discarded
df_final_discard.to_csv(r'D:\LZY\Projects\investAtlanta26\Organize\discarded_businesses.csv', index=False)

# Print Summary
print(f"Anchors Found (Publix/Kroger/Target etc.): {len(df_chain_keep)}")
print(f"Total High Confidence Fresh Food Points: {len(df_final_keep)}")
print(f"Corner Stores/Maybes requiring Manual Audit: {len(df_requires_review)}")