import pandas as pd
import random

# ============================================================
# STEP 1: ADD PRODUCT NAMES TO RECOMMENDATIONS
# ============================================================

def add_product_names_to_recommendations():
    """
    Adds product names and details to make recommendations readable
    """
    print("=" * 80)
    print("STEP 1: ADDING PRODUCT NAMES TO RECOMMENDATIONS")
    print("=" * 80)
    
    # Load the data
    print("\n📂 Loading data files...")
    recommendations = pd.read_csv('recommendations.csv')
    products = pd.read_csv('products.csv')
    customers = pd.read_csv('customers.csv')
    
    print(f"✅ Loaded {len(recommendations)} recommendations")
    print(f"✅ Loaded {len(products)} products")
    print(f"✅ Loaded {len(customers)} customers")
    
    # Merge product details for recommended product
    print("\n🔗 Adding product names for recommended products...")
    recommendations_enriched = recommendations.merge(
        products[['product_id', 'product_name', 'brand', 'l2_category', 'l3_category', 'unit_price']],
        left_on='recommended_product',
        right_on='product_id',
        how='left'
    )
    
    # Rename columns for clarity
    recommendations_enriched = recommendations_enriched.rename(columns={
        'product_name': 'recommended_product_name',
        'brand': 'recommended_brand',
        'l2_category': 'recommended_category',
        'l3_category': 'recommended_subcategory',
        'unit_price': 'recommended_price'
    })
    
    # Merge product details for trigger product
    print("🔗 Adding product names for trigger products...")
    recommendations_enriched = recommendations_enriched.merge(
        products[['product_id', 'product_name', 'brand', 'l2_category', 'l3_category']],
        left_on='trigger_product',
        right_on='product_id',
        how='left',
        suffixes=('', '_trigger')
    )
    
    # Rename trigger columns
    recommendations_enriched = recommendations_enriched.rename(columns={
        'product_name': 'trigger_product_name',
        'brand': 'trigger_brand',
        'l2_category': 'trigger_category',
        'l3_category': 'trigger_subcategory'
    })
    
    # Add customer details
    print("🔗 Adding customer names...")
    recommendations_enriched = recommendations_enriched.merge(
        customers[['customer_id', 'customer_name', 'end_use', 'customer_type', 'city', 'state']],
        on='customer_id',
        how='left'
    )
    
    # Create a human-readable reason
    recommendations_enriched['readable_reason'] = (
        recommendations_enriched['trigger_product_name'] + 
        " → " + 
        recommendations_enriched['recommended_product_name'] +
        f" (confidence: " +
        (recommendations_enriched['confidence'] * 100).round(0).astype(int).astype(str) + "%)"
    )
    
    # Reorder columns for readability
    columns_order = [
        'customer_id', 'customer_name', 'city', 'state', 'end_use', 'customer_type',
        'rank', 'score',
        'recommended_product', 'recommended_product_name', 'recommended_brand', 
        'recommended_category', 'recommended_subcategory', 'recommended_price',
        'recommended_qty',
        'trigger_product', 'trigger_product_name', 'trigger_brand',
        'trigger_category', 'trigger_subcategory',
        'support', 'confidence',
        'readable_reason',
        'cluster_id', 'segment'
    ]
    
    # Keep only columns that exist
    columns_order = [col for col in columns_order if col in recommendations_enriched.columns]
    recommendations_enriched = recommendations_enriched[columns_order]
    
    # Save enriched recommendations
    recommendations_enriched.to_csv('recommendations_with_names.csv', index=False)
    print(f"\n✅ Enriched recommendations saved to: recommendations_with_names.csv")
    print(f"✅ Total rows: {len(recommendations_enriched)}")
    
    return recommendations_enriched


# ============================================================
# STEP 2: ANALYZE 10 SAMPLE CUSTOMERS
# ============================================================

def analyze_sample_customers(recommendations_enriched, num_samples=10):
    """
    Analyzes 10 random customers to validate if recommendations make business sense
    """
    print("\n" + "=" * 80)
    print("STEP 2: ANALYZING 10 SAMPLE CUSTOMERS")
    print("=" * 80)
    
    # Load market basket to see what customers actually bought
    print("\n📂 Loading customer purchase history...")
    market_basket = pd.read_csv('market_basket.csv')
    
    # Get unique customers from recommendations
    unique_customers = recommendations_enriched['customer_id'].unique()
    
    # Sample 10 random customers
    random.seed(42)
    sample_customers = random.sample(list(unique_customers), min(num_samples, len(unique_customers)))
    
    print(f"\n🎲 Randomly selected {len(sample_customers)} customers for validation\n")
    
    validation_report = []
    
    for idx, customer_id in enumerate(sample_customers, 1):
        print("=" * 80)
        print(f"CUSTOMER {idx}/{len(sample_customers)}: {customer_id}")
        print("=" * 80)
        
        # Get customer info
        cust_info = recommendations_enriched[
            recommendations_enriched['customer_id'] == customer_id
        ].iloc[0]
        
        print(f"\n📋 CUSTOMER PROFILE:")
        print(f"  • Name: {cust_info['customer_name']}")
        print(f"  • Location: {cust_info['city']}, {cust_info['state']}")
        print(f"  • Business Type: {cust_info['end_use']}")
        print(f"  • Customer Type: {cust_info['customer_type']}")
        print(f"  • Segment: {cust_info['segment']}")
        print(f"  • Cluster: {cust_info['cluster_id']}")
        
        # Get what they actually bought
        customer_purchases = market_basket[market_basket['customer_id'] == customer_id]
        
        if len(customer_purchases) > 0:
            print(f"\n🛒 PURCHASE HISTORY (by Category):")
            category_summary = customer_purchases.groupby('l2_category').agg({
                'total_quantity': 'sum',
                'purchase_frequency': 'sum'
            }).sort_values('total_quantity', ascending=False)
            
            for cat, row in category_summary.head(5).iterrows():
                print(f"  • {cat}: {int(row['total_quantity'])} units ({int(row['purchase_frequency'])} purchases)")
            
            # Show specific products
            print(f"\n🔍 TOP PRODUCTS PURCHASED:")
            top_products = customer_purchases.nlargest(5, 'total_quantity')[
                ['product_id', 'l2_category', 'l3_category', 'total_quantity']
            ]
            for _, prod in top_products.iterrows():
                print(f"  • {prod['product_id']}: {prod['l3_category']} ({prod['l2_category']}) - {int(prod['total_quantity'])} units")
        else:
            print("\n⚠️  No purchase history found in market basket")
        
        # Get recommendations for this customer
        customer_recs = recommendations_enriched[
            recommendations_enriched['customer_id'] == customer_id
        ].sort_values('rank')
        
        print(f"\n🎯 TOP 5 RECOMMENDATIONS:")
        for _, rec in customer_recs.iterrows():
            print(f"\n  Rank {int(rec['rank'])}:")
            print(f"    Product: {rec['recommended_product_name']}")
            print(f"    Brand: {rec['recommended_brand']}")
            print(f"    Category: {rec['recommended_subcategory']} ({rec['recommended_category']})")
            print(f"    Price: ${rec['recommended_price']}")
            print(f"    Qty: {rec['recommended_qty']} units")
            print(f"    Score: {rec['score']:.3f}")
            print(f"    Confidence: {rec['confidence']*100:.0f}%")
            print(f"    Why: {rec['trigger_product_name']} → {rec['recommended_product_name']}")
        
        # Business sense validation
        print(f"\n✅ BUSINESS SENSE CHECK:")
        
        # Check 1: Do recommendations match customer's end_use?
        rec_categories = customer_recs['recommended_category'].unique()
        print(f"\n  1. Recommendation Categories: {', '.join(rec_categories)}")
        
        # Check 2: Are categories aligned with end_use?
        end_use = cust_info['end_use']
        expected_categories = {
            'General Construction': ['Power Tools', 'Hand Tools', 'Fasteners', 'Building Materials'],
            'Residential Construction': ['Power Tools', 'Hand Tools', 'Fasteners', 'Building Materials'],
            'Painting': ['Paints & Coatings', 'Painting Supplies', 'Hand Tools'],
            'Plumbing': ['Plumbing', 'Hand Tools', 'Power Tools', 'Adhesives & Sealants'],
            'Electrical': ['Electrical', 'Power Tools', 'Hand Tools'],
            'HVAC': ['HVAC', 'Electrical', 'Hand Tools'],
            'Flooring': ['Building Materials', 'Adhesives & Sealants', 'Power Tools'],
            'Roofing': ['Building Materials', 'Fasteners', 'Power Tools', 'Safety Equipment'],
        }
        
        expected = expected_categories.get(end_use, [])
        matches = [cat for cat in rec_categories if cat in expected]
        
        if matches:
            print(f"  2. ✅ Categories match end_use ({end_use}): {', '.join(matches)}")
        else:
            print(f"  2. ⚠️  Categories don't strongly match end_use ({end_use})")
        
        # Check 3: Score distribution
        avg_score = customer_recs['score'].mean()
        max_score = customer_recs['score'].max()
        min_score = customer_recs['score'].min()
        print(f"  3. Score Range: {min_score:.3f} to {max_score:.3f} (avg: {avg_score:.3f})")
        
        if max_score >= 0.4:
            print(f"     ✅ Has strong recommendations (top score: {max_score:.3f})")
        elif max_score >= 0.3:
            print(f"     ⚠️  Moderate recommendations (top score: {max_score:.3f})")
        else:
            print(f"     ❌ Weak recommendations (top score: {max_score:.3f})")
        
        # Check 4: Confidence distribution
        avg_conf = customer_recs['confidence'].mean()
        print(f"  4. Average Confidence: {avg_conf*100:.0f}%")
        
        if avg_conf >= 0.5:
            print(f"     ✅ High confidence recommendations")
        elif avg_conf >= 0.3:
            print(f"     ⚠️  Moderate confidence")
        else:
            print(f"     ❌ Low confidence")
        
        # Store validation summary
        validation_report.append({
            'customer_id': customer_id,
            'customer_name': cust_info['customer_name'],
            'end_use': end_use,
            'segment': cust_info['segment'],
            'cluster': cust_info['cluster_id'],
            'avg_score': avg_score,
            'max_score': max_score,
            'avg_confidence': avg_conf,
            'categories_match': len(matches) > 0,
            'quality': 'High' if max_score >= 0.4 else ('Medium' if max_score >= 0.3 else 'Low')
        })
        
        print("\n")
    
    # Summary report
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    validation_df = pd.DataFrame(validation_report)
    
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"  • Customers Analyzed: {len(validation_df)}")
    print(f"  • Average Score: {validation_df['avg_score'].mean():.3f}")
    print(f"  • Average Max Score: {validation_df['max_score'].mean():.3f}")
    print(f"  • Average Confidence: {validation_df['avg_confidence'].mean()*100:.0f}%")
    print(f"  • Categories Match End-Use: {validation_df['categories_match'].sum()}/{len(validation_df)} ({validation_df['categories_match'].sum()/len(validation_df)*100:.0f}%)")
    
    print(f"\n📈 QUALITY DISTRIBUTION:")
    quality_dist = validation_df['quality'].value_counts()
    for quality, count in quality_dist.items():
        print(f"  • {quality}: {count}/{len(validation_df)} ({count/len(validation_df)*100:.0f}%)")
    
    # Save validation report
    validation_df.to_csv('validation_report.csv', index=False)
    print(f"\n✅ Validation report saved to: validation_report.csv")
    
    return validation_df


# ============================================================
# STEP 3: CREATE SALESPERSON-FRIENDLY REPORT
# ============================================================

def create_salesperson_report(recommendations_enriched, num_samples=10):
    """
    Creates a simple, readable report for salespeople
    """
    print("\n" + "=" * 80)
    print("STEP 3: CREATING SALESPERSON-FRIENDLY REPORT")
    print("=" * 80)
    
    # Sample customers
    unique_customers = recommendations_enriched['customer_id'].unique()
    random.seed(42)
    sample_customers = random.sample(list(unique_customers), min(num_samples, len(unique_customers)))
    
    # Create simple report
    report_rows = []
    
    for customer_id in sample_customers:
        customer_recs = recommendations_enriched[
            recommendations_enriched['customer_id'] == customer_id
        ].sort_values('rank')
        
        cust_info = customer_recs.iloc[0]
        
        for _, rec in customer_recs.iterrows():
            report_rows.append({
                'Customer': cust_info['customer_name'],
                'Location': f"{cust_info['city']}, {cust_info['state']}",
                'Business Type': cust_info['end_use'],
                'Rank': int(rec['rank']),
                'Recommended Product': rec['recommended_product_name'],
                'Brand': rec['recommended_brand'],
                'Category': rec['recommended_subcategory'],
                'Price': f"${rec['recommended_price']}",
                'Suggested Qty': int(rec['recommended_qty']),
                'Confidence': f"{rec['confidence']*100:.0f}%",
                'Why': f"Similar to {rec['trigger_product_name']}"
            })
    
    report_df = pd.DataFrame(report_rows)
    report_df.to_csv('salesperson_report.csv', index=False)
    
    print(f"\n✅ Salesperson report created: salesperson_report.csv")
    print(f"✅ Contains {len(report_df)} recommendations for {len(sample_customers)} customers")
    
    # Print a sample
    print(f"\n📄 SAMPLE FROM SALESPERSON REPORT:\n")
    print(report_df.head(10).to_string(index=False))
    
    return report_df


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    print("\n")
    print("*" * 80)
    print("RECOMMENDATION VALIDATION & ENRICHMENT TOOL")
    print("*" * 80)
    print("\nThis tool will:")
    print("  1. Add product names to recommendations")
    print("  2. Validate 10 sample customers")
    print("  3. Create a salesperson-friendly report")
    print("\n")
    
    # Step 1: Add product names
    recommendations_enriched = add_product_names_to_recommendations()
    
    # Step 2: Analyze sample customers
    validation_df = analyze_sample_customers(recommendations_enriched, num_samples=10)
    
    # Step 3: Create salesperson report
    salesperson_report = create_salesperson_report(recommendations_enriched, num_samples=10)
    
    print("\n" + "=" * 80)
    print("✅ ALL TASKS COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print("\nGenerated Files:")
    print("  1. recommendations_with_names.csv - Full enriched recommendations")
    print("  2. validation_report.csv - Quality analysis for 10 customers")
    print("  3. salesperson_report.csv - Simple report for sales team")
    print("\nNext Steps:")
    print("  • Review the validation report to check quality")
    print("  • Share salesperson_report.csv with your sales team")
    print("  • Collect feedback (High/Medium/Low ratings)")
    print("  • Use feedback to improve recommendations!")
    print("\n")