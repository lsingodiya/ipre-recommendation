# Understanding Clustering with REALISTIC Data

## 📊 THE REAL DATA

### 1️⃣ CUSTOMERS (customers.csv)

```
customer_id | region    | end_use      | customer_name                    | customer_type
------------|-----------|--------------|----------------------------------|---------------
C001        | Northeast | Construction | BuildRight Contractors LLC       | Commercial
C002        | Northeast | Construction | HomeWorks General Contracting    | Commercial
C003        | Northeast | Painting     | ProPaint Services Inc            | Commercial
C004        | Northeast | Painting     | ColorSplash Painters             | Small Business
C005        | Northeast | Plumbing     | QuickFix Plumbing                | Small Business
C006        | Southeast | Construction | Southern Builders Co             | Commercial
C007        | Southeast | Construction | Apex Construction Group          | Commercial
C008        | Southeast | Electrical   | Bright Electric Solutions        | Commercial
C009        | Southeast | Painting     | Coastal Painters LLC             | Small Business
C010        | Southeast | HVAC         | CoolAir Systems                  | Commercial
```

**What this means:**
- C001 = BuildRight Contractors (Construction company in Northeast)
- C003 = ProPaint Services (Painting company in Northeast)
- C005 = QuickFix Plumbing (Plumbing company in Northeast)

---

### 2️⃣ PRODUCTS (products.csv)

```
product_id | brand          | l2_category      | l3_category        | product_name
-----------|----------------|------------------|--------------------|----------------------------------------
P001       | DeWalt         | Power Tools      | Cordless Drills    | DeWalt 20V MAX Cordless Drill Kit
P002       | DeWalt         | Power Tools      | Circular Saws      | DeWalt 7-1/4 Circular Saw
P003       | Milwaukee      | Power Tools      | Impact Drivers     | Milwaukee M18 Impact Driver
P006       | Stanley        | Hand Tools       | Hammers            | Stanley 16oz Claw Hammer
P007       | Stanley        | Hand Tools       | Tape Measures      | Stanley 25ft Tape Measure
P011       | Grip-Rite      | Fasteners        | Framing Nails      | Grip-Rite 3-Inch Framing Nails 5lb
P012       | Grip-Rite      | Fasteners        | Finishing Nails    | Grip-Rite 2-Inch Finishing Nails 5lb
P016       | Behr           | Paints           | Interior Paint     | Behr Premium Plus Interior Paint Gallon
P017       | Behr           | Paints           | Exterior Paint     | Behr Premium Plus Exterior Paint Gallon
P021       | Purdy          | Painting Supplies| Paint Brushes      | Purdy 2.5-Inch Angle Brush
P022       | Wooster        | Painting Supplies| Paint Rollers      | Wooster 9-Inch Roller Cover 3-Pack
P026       | SharkBite      | Plumbing         | Pipe Fittings      | SharkBite 1/2-Inch Push Fittings
P027       | Charlotte Pipe | Plumbing         | PVC Pipes          | Charlotte 3-Inch PVC Pipe 10ft
P031       | Southwire      | Electrical       | Romex Wire         | Southwire 14/2 Romex 250ft
P032       | Leviton        | Electrical       | Outlets            | Leviton Duplex Outlets 10-Pack
```

**L2 Categories Explained:**
- **Power Tools** = Drills, Saws, Impact Drivers (things that need electricity)
- **Hand Tools** = Hammers, Tape Measures, Screwdrivers (manual tools)
- **Fasteners** = Nails, Screws (things that hold stuff together)
- **Paints** = Interior/Exterior paints
- **Painting Supplies** = Brushes, Rollers, Tape
- **Plumbing** = Pipes, Fittings, Faucets
- **Electrical** = Wires, Outlets, Switches

---

### 3️⃣ INVOICES (invoices.csv) - Sample

```
customer_id | product_id | quantity | invoice_date
------------|------------|----------|-------------
C001        | P001       | 4        | 2024-01-31     <- BuildRight bought 4 DeWalt Drills
C001        | P015       | 47       | 2024-02-16     <- BuildRight bought 47 Structural Screws
C001        | P007       | 22       | 2024-03-21     <- BuildRight bought 22 Tape Measures
C001        | P012       | 22       | 2024-03-22     <- BuildRight bought 22 Finishing Nails
C001        | P006       | 3        | 2024-03-30     <- BuildRight bought 3 Hammers
C001        | P004       | 2        | 2024-04-14     <- BuildRight bought 2 Reciprocating Saws
C003        | P016       | 25       | 2024-02-10     <- ProPaint bought 25 Interior Paint gallons
C003        | P021       | 18       | 2024-02-10     <- ProPaint bought 18 Paint Brushes
C003        | P022       | 30       | 2024-02-15     <- ProPaint bought 30 Roller Covers
C003        | P017       | 40       | 2024-03-20     <- ProPaint bought 40 Exterior Paint gallons
C005        | P026       | 15       | 2024-01-15     <- QuickFix bought 15 Pipe Fittings
C005        | P027       | 8        | 2024-01-20     <- QuickFix bought 8 PVC Pipes
C005        | P029       | 3        | 2024-02-10     <- QuickFix bought 3 Kitchen Faucets
```

---

## 🔄 STEP-BY-STEP: HOW CLUSTERING WORKS

### STEP 1: Market Basket Creation

**Code does this:**
```python
# Join all three files together
df = invoices.merge(products).merge(customers)

# Group by customer and product to get totals
grouped = df.groupby([
    'customer_id', 'region', 'end_use', 
    'product_id', 'l2_category'
]).agg({
    'quantity': 'sum',
    'invoice_date': 'count'  # how many times purchased
})
```

**Result - Market Basket for C001 (BuildRight Contractors):**

```
customer_id: C001
customer_name: BuildRight Contractors LLC
region: Northeast
end_use: Construction

Products purchased:
┌────────────┬─────────────────┬─────────────┬──────────┬───────────┐
│ product_id │ l2_category     │ product_name│ quantity │ times_buy │
├────────────┼─────────────────┼─────────────┼──────────┼───────────┤
│ P001       │ Power Tools     │ Drills      │ 13       │ 2         │
│ P002       │ Power Tools     │ Circular Saw│ 7        │ 1         │
│ P003       │ Power Tools     │ Impact Drive│ 2        │ 1         │
│ P004       │ Power Tools     │ Recip Saw   │ 2        │ 1         │
│ P005       │ Power Tools     │ Grinder     │ 6        │ 1         │
│ P006       │ Hand Tools      │ Hammer      │ 3        │ 1         │
│ P007       │ Hand Tools      │ Tape Measure│ 22       │ 1         │
│ P010       │ Hand Tools      │ Wire Strip  │ 8        │ 1         │
│ P011       │ Fasteners       │ Framing Nail│ 0        │ 0         │
│ P012       │ Fasteners       │ Finish Nail │ 90       │ 2         │
│ P013       │ Fasteners       │ Const Screws│ 147      │ 2         │
│ P014       │ Fasteners       │ Concrete Scr│ 53       │ 1         │
│ P015       │ Fasteners       │ Struct Screw│ 146      │ 2         │
│ P041       │ Fasteners       │ Joist Hanger│ 67       │ 2         │
│ P046       │ Building Mater. │ Plywood     │ 45       │ 1         │
│ P050       │ Power Tools     │ Nail Gun    │ 5        │ 1         │
└────────────┴─────────────────┴─────────────┴──────────┴───────────┘

SUMMARY BY L2 CATEGORY:
Power Tools: 35 units total
Hand Tools: 33 units total  
Fasteners: 503 units total  ← LOTS of nails and screws!
Building Materials: 45 units total
```

**Result - Market Basket for C003 (ProPaint Services):**

```
customer_id: C003
customer_name: ProPaint Services Inc
region: Northeast
end_use: Painting

Products purchased:
┌────────────┬──────────────────┬─────────────┬──────────┬───────────┐
│ product_id │ l2_category      │ product_name│ quantity │ times_buy │
├────────────┼──────────────────┼─────────────┼──────────┼───────────┤
│ P016       │ Paints           │ Interior    │ 95       │ 4         │
│ P017       │ Paints           │ Exterior    │ 120      │ 3         │
│ P018       │ Paints           │ Primer      │ 50       │ 2         │
│ P020       │ Paints           │ Regal Select│ 30       │ 1         │
│ P021       │ Painting Supplies│ Brushes     │ 48       │ 3         │
│ P022       │ Painting Supplies│ Rollers     │ 75       │ 3         │
│ P023       │ Painting Supplies│ Tape        │ 12       │ 2         │
│ P025       │ Painting Supplies│ Drop Cloths │ 8        │ 1         │
│ P007       │ Hand Tools       │ Tape Measure│ 3        │ 1         │
└────────────┴──────────────────┴─────────────┴──────────┴───────────┘

SUMMARY BY L2 CATEGORY:
Paints: 295 units total           ← LOTS of paint!
Painting Supplies: 143 units total ← LOTS of brushes/rollers!
Hand Tools: 3 units total          ← Very few hand tools
```

**Result - Market Basket for C005 (QuickFix Plumbing):**

```
customer_id: C005
customer_name: QuickFix Plumbing
region: Northeast  
end_use: Plumbing

Products purchased:
┌────────────┬─────────────┬─────────────┬──────────┬───────────┐
│ product_id │ l2_category │ product_name│ quantity │ times_buy │
├────────────┼─────────────┼─────────────┼──────────┼───────────┤
│ P026       │ Plumbing    │ Pipe Fittng │ 85       │ 6         │
│ P027       │ Plumbing    │ PVC Pipes   │ 42       │ 5         │
│ P028       │ Plumbing    │ PVC Cement  │ 15       │ 3         │
│ P029       │ Plumbing    │ Faucets     │ 12       │ 4         │
│ P030       │ Plumbing    │ Shower Heads│ 8        │ 2         │
│ P006       │ Hand Tools  │ Hammer      │ 5        │ 2         │
│ P009       │ Hand Tools  │ Pliers      │ 8        │ 2         │
│ P001       │ Power Tools │ Drill       │ 2        │ 1         │
│ P011       │ Fasteners   │ Framing Nail│ 10       │ 1         │
└────────────┴─────────────┴─────────────┴──────────┴───────────┘

SUMMARY BY L2 CATEGORY:
Plumbing: 162 units total     ← LOTS of plumbing supplies!
Hand Tools: 13 units total
Power Tools: 2 units total
Fasteners: 10 units total
```

---

### STEP 2: Create Pivot Table (The KEY Step!)

**This is what the code does:**

```python
# For Northeast_Construction segment only:
# (includes C001, C002, etc.)

pivot = df.pivot_table(
    index='customer_id',
    columns='l2_category',
    values='total_quantity',
    aggfunc='sum',
    fill_value=0
)
```

**Result - Pivot Table for Northeast Customers:**

```
CUSTOMER SHOPPING PATTERNS (by L2 Category quantities)

            │ Power  │ Hand   │ Fasteners │ Building │ Paints │ Painting │ Plumbing │ Electrical │
            │ Tools  │ Tools  │           │ Materials│        │ Supplies │          │            │
────────────┼────────┼────────┼───────────┼──────────┼────────┼──────────┼──────────┼────────────┤
C001        │   35   │   33   │    503    │    45    │    0   │     0    │     0    │      0     │
(BuildRight)│        │        │           │          │        │          │          │            │
────────────┼────────┼────────┼───────────┼──────────┼────────┼──────────┼──────────┼────────────┤
C002        │   28   │   25   │    425    │    38    │    0   │     0    │     0    │      0     │
(HomeWorks) │        │        │           │          │        │          │          │            │
────────────┼────────┼────────┼───────────┼──────────┼────────┼──────────┼──────────┼────────────┤
C003        │    0   │    3   │      0    │     0    │  295   │    143   │     0    │      0     │
(ProPaint)  │        │        │           │          │        │          │          │            │
────────────┼────────┼────────┼───────────┼──────────┼────────┼──────────┼──────────┼────────────┤
C004        │    0   │    5   │      0    │     0    │  220   │    115   │     0    │      0     │
(ColorSplsh)│        │        │           │          │        │          │          │            │
────────────┼────────┼────────┼───────────┼──────────┼────────┼──────────┼──────────┼────────────┤
C005        │    2   │   13   │     10    │     0    │    0   │     0    │    162   │      0     │
(QuickFix)  │        │        │           │          │        │          │          │            │
────────────┴────────┴────────┴───────────┴──────────┴────────┴──────────┴──────────┴────────────┘
```

**NOW WE CAN SEE THE PATTERNS!**

👀 **Looking at this table, YOU can see:**
- C001 & C002 have SIMILAR patterns (Power Tools, Hand Tools, LOTS of Fasteners, Building Materials)
- C003 & C004 have SIMILAR patterns (Paints, Painting Supplies, almost nothing else)
- C005 has a UNIQUE pattern (Plumbing, some Hand Tools, very different!)

---

### STEP 3: K-Means Clustering - THE MAGIC!

**The computer does MATH to find these patterns automatically:**

```python
# Calculate how many clusters to make
n = 5 customers
k = min(4, int(√5)) = min(4, 2) = 2 clusters

# K-Means algorithm starts:
```

**Iteration 1: Pick Random Centers**
```
Let's say computer randomly picks:
Center 1: Start near C001's pattern
Center 2: Start near C003's pattern
```

**Iteration 2: Assign Customers to Nearest Center**

For each customer, calculate distance to each center:

```
C001's pattern: [35, 33, 503, 45, 0, 0, 0, 0]
Center 1:       [35, 33, 503, 45, 0, 0, 0, 0]
Distance = √[(35-35)² + (33-33)² + (503-503)² + ...] = 0 (PERFECT MATCH!)

C001's pattern: [35, 33, 503, 45, 0, 0, 0, 0]
Center 2:       [0, 3, 0, 0, 295, 143, 0, 0]
Distance = √[(35-0)² + (33-3)² + (503-0)² + (45-0)² + (0-295)² + (0-143)²]
         = √[1225 + 900 + 253009 + 2025 + 87025 + 20449]
         = √364633
         = 604 (VERY FAR!)

So C001 → Cluster 0 (close to Center 1) ✅
```

Same for others:
```
C002 → Calculate distances → Cluster 0 ✅ (similar to C001)
C003 → Calculate distances → Cluster 1 ✅ (far from C001, close to C003)
C004 → Calculate distances → Cluster 1 ✅ (similar to C003)
C005 → Calculate distances → Cluster 0 ✅ (has some tools/fasteners)
```

**Iteration 3: Move Centers**
```
New Center 0 = Average of C001, C002, C005
             = [(35+28+2)/3, (33+25+13)/3, (503+425+10)/3, ...]
             = [21.7, 23.7, 312.7, ...]

New Center 1 = Average of C003, C004
             = [(0+0)/2, (3+5)/2, (0+0)/2, (0+0)/2, (295+220)/2, (143+115)/2, ...]
             = [0, 4, 0, 0, 257.5, 129, ...]
```

**Iteration 4: Re-assign (check if anyone moves)**
- Calculate distances again with new centers
- If nobody moves clusters → DONE! ✅

---

### STEP 4: FINAL CLUSTER ASSIGNMENTS

```
CLUSTER 0 (Construction/Plumbing Workers):
├── C001 - BuildRight Contractors
├── C002 - HomeWorks General Contracting  
└── C005 - QuickFix Plumbing

Common pattern: Buy Power Tools, Hand Tools, Fasteners
Cluster center pattern: [21.7, 23.7, 312.7, 27.7, 0, 0, 54, 0]


CLUSTER 1 (Painters):
├── C003 - ProPaint Services
└── C004 - ColorSplash Painters

Common pattern: Buy LOTS of Paints and Painting Supplies
Cluster center pattern: [0, 4, 0, 0, 257.5, 129, 0, 0]
```

---

## 🎯 WHY L2 CATEGORIES?

### ❌ If we used INDIVIDUAL PRODUCTS:

```
Customer | P001 | P002 | P003 | P004 | P005 | P006 | ... | P050
---------|------|------|------|------|------|------|-----|------
C001     |  13  |   7  |   2  |   2  |   6  |   3  | ... |   5
C002     |   8  |   5  |   0  |   4  |   3  |   2  | ... |   0
C003     |   0  |   0  |   0  |   0  |   0  |   0  | ... |   0
```

**Problems:**
- 50 columns (one for each product!)
- Most values are 0 (C003 doesn't buy power tools at all)
- Can't see the PATTERN - too detailed
- Computer gets confused by all the zeros

### ✅ Using L2 CATEGORIES:

```
Customer | Power Tools | Hand Tools | Fasteners | Paints | Painting Supplies
---------|-------------|------------|-----------|--------|------------------
C001     |     35      |     33     |    503    |    0   |        0
C002     |     28      |     25     |    425    |    0   |        0
C003     |      0      |      3     |      0    |   295  |       143
```

**Benefits:**
- Only 8 columns (manageable!)
- Clear patterns emerge (construction vs painting)
- No confusion - numbers are meaningful
- Computer can easily see who's similar

---

## 💡 THE AH-HA MOMENT

**L2 Categories are like asking:**

❌ "What specific drill model did you buy?" (too detailed)
✅ "Do you buy power tools or paints?" (just right!)
❌ "What department are you in?" (too broad)

**It's the Goldilocks level - not too specific, not too broad, JUST RIGHT!**

---

## 🎓 COMPLETE EXAMPLE SUMMARY

### What We Started With:
```
847 invoice records showing:
- C001 bought P001 (drill) 4 units
- C001 bought P012 (nails) 22 units
- C003 bought P016 (paint) 25 units
... and so on
```

### After Market Basket:
```
Each customer has a shopping summary:
C001: Power Tools (35), Hand Tools (33), Fasteners (503), Building Materials (45)
C003: Paints (295), Painting Supplies (143), Hand Tools (3)
C005: Plumbing (162), Hand Tools (13), Power Tools (2), Fasteners (10)
```

### After Clustering:
```
Cluster 0: Construction/Trade workers (C001, C002, C005)
  → They buy tools, fasteners, building materials

Cluster 1: Painters (C003, C004)
  → They buy paints and painting supplies
```

### Why This Matters:
```
When C001 (BuildRight Contractors) needs a recommendation:
✅ Look at what OTHER people in Cluster 0 bought
   → If C002 bought P050 (Nail Gun), suggest it to C001!
   
❌ DON'T look at what Cluster 1 (Painters) bought
   → C003 bought paint brushes - NOT relevant for C001!
```

---

## 🎉 FINAL ANSWER TO YOUR QUESTION

**Q: On what BASIS are we clustering?**  
**A:** L2 product category purchase quantities

**Q: How do we decide which cluster?**  
**A:** Mathematical distance - customers with SIMILAR L2 category patterns go together

**The Real Magic:**
1. Convert messy invoices → Clean L2 category totals
2. Use math (K-Means) to find similar customers
3. Group them into clusters
4. Use clusters to make relevant recommendations

**Simple Version:**
"Show me customers who buy similar TYPES of products, so I can recommend products that worked for similar customers!"

Does this make WAY more sense now with real product names and real patterns? 🙂
