import streamlit as st
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import io
import math

# ==========================================
# 1. Calculation Logic
# ==========================================

def calculate_common_rates(inputs):
    """Calculates the standard Cost Per Kg applicable to all components from this tool."""
    data = {}
    
    # --- Material Cost ---
    try:
        data['yield_pct'] = inputs['yield_pct']
        # Gross Weight required to get 1 Kg of Net Output
        data['gross_weight'] = 1 / (inputs['yield_pct'] / 100) if inputs['yield_pct'] > 0 else 0
        data['net_weight'] = 1.0 
        data['scrap_weight'] = data['gross_weight'] - 1.0
        
        data['rm_rate'] = inputs['rm_rate']
        data['rm_cost'] = data['gross_weight'] * data['rm_rate']
        
        data['scrap_rate'] = inputs['scrap_rate']
        data['scrap_recovery'] = data['scrap_weight'] * data['scrap_rate']
        
        data['nrm'] = data['rm_cost'] - data['scrap_recovery'] # Net Material Cost
    except ZeroDivisionError:
        data.update({'gross_weight':0, 'scrap_weight':0, 'rm_cost':0, 'scrap_recovery':0, 'nrm':0})

    # --- Processing Cost ---
    # Strokes per Kg = 1000 / (Total Weight of all components produced in 1 stroke)
    try:
        if inputs['weight_per_stroke_g'] > 0:
            raw_strokes = 1000 / inputs['weight_per_stroke_g']
            data['strokes_per_kg'] = math.ceil(raw_strokes) # Rounded UP
        else:
            data['strokes_per_kg'] = 0
            
        data['stroke_rate'] = inputs['stroke_rate']
        data['process_cost'] = data['strokes_per_kg'] * data['stroke_rate']
    except:
        data['process_cost'] = 0

    # --- Overheads ---
    data['inventory_cost'] = data['nrm'] * (inputs['inventory_pct'] / 100)
    data['rejection_cost'] = data['nrm'] * (inputs['rejection_pct'] / 100)
    data['overhead_cost'] = data['process_cost'] * (inputs['overhead_pct'] / 100)
    data['profit_cost'] = data['nrm'] * (inputs['profit_pct'] / 100)

    # --- Total Common Cost ---
    data['total_cost_per_kg'] = (
        data['nrm'] + 
        data['process_cost'] + 
        data['inventory_cost'] + 
        data['rejection_cost'] + 
        data['overhead_cost'] + 
        data['profit_cost']
    )
    
    return data

def calculate_component_cost(common_data, comp_input, packing_rate, transport_rate):
    """Calculates specific stack cost for a single component using the common rate."""
    c_data = comp_input.copy()
    
    # 1. Stack Specifications
    if c_data['sheet_thickness'] > 0:
        c_data['lams_per_stack'] = c_data['stack_height'] / c_data['sheet_thickness']
    else:
        c_data['lams_per_stack'] = 0
        
    c_data['stack_weight_g'] = c_data['lams_per_stack'] * c_data['single_lam_weight_g']
    c_data['stack_weight_kg'] = c_data['stack_weight_g'] / 1000
    
    # 2. Base Cost (Material + Process)
    c_data['base_stack_cost'] = c_data['stack_weight_kg'] * common_data['total_cost_per_kg']
    
    # 3. Specific Fixed Costs
    
    # Riveting
    rivet_mat_cost = c_data['rivet_unit_cost'] * c_data['rivet_count']
    c_data['rivet_total_cost'] = rivet_mat_cost + c_data['rivet_manpower_cost']
    
    # Tool Maintenance 
    if 'tool_maint_cost' not in c_data:
         c_data['tool_maint_cost'] = 0.03 * c_data['lams_per_stack']

    # 4. Total Manufacturing Cost
    c_data['stack_mfg_cost'] = (
        c_data['base_stack_cost'] + 
        c_data['rivet_total_cost'] + 
        c_data['pressing_cost'] + 
        c_data['tool_maint_cost']
    )
    
    # 5. Packing & Transport
    c_data['packing_cost'] = c_data['stack_weight_kg'] * packing_rate
    c_data['transport_cost'] = c_data['stack_weight_kg'] * transport_rate
    
    # 6. Final Landed Cost
    c_data['final_stack_cost'] = c_data['stack_mfg_cost'] + c_data['packing_cost'] + c_data['transport_cost']
    
    return c_data

# ==========================================
# 2. PDF Generation Functions
# ==========================================

def create_detailed_pdf(common_data, components_data, common_inputs):
    """Generates the comprehensive report with all breakdowns."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=1, fontSize=16, spaceAfter=12)
    header_style = ParagraphStyle('Header', parent=styles['Heading2'], spaceBefore=12, spaceAfter=6)
    
    # --- Title ---
    elements.append(Paragraph("Sai Precision Tool Industries", title_style))
    elements.append(Paragraph(f"Detailed Costing Report: {common_inputs['tool_ref_name']}", styles['Normal']))
    elements.append(Spacer(1, 10))

    # --- Section 1: Common Cost Per Kg ---
    elements.append(Paragraph("1. Common Manufacturing Cost per Kg", header_style))
    
    common_table_data = [
        ["Parameter", "Value", "Unit"],
        ["Yield", f"{common_inputs['yield_pct']:.2f}", "%"],
        ["Raw Material Rate", f"{common_inputs['rm_rate']:.2f}", "Rs/Kg"],
        ["Scrap Rate", f"{common_inputs['scrap_rate']:.2f}", "Rs/Kg"],
        ["Net Material Cost (NRM)", f"{common_data['nrm']:.2f}", "Rs/Kg"],
        ["Strokes per Kg (Rounded Up)", f"{common_data['strokes_per_kg']}", "Nos"],
        ["Processing Cost", f"{common_data['process_cost']:.2f}", "Rs/Kg"],
        ["Overheads (Inv, Rej, OH)", f"{common_data['inventory_cost']+common_data['rejection_cost']+common_data['overhead_cost']:.2f}", "Rs/Kg"],
        ["Profit", f"{common_data['profit_cost']:.2f}", "Rs/Kg"],
        ["TOTAL MFG COST PER KG", f"{common_data['total_cost_per_kg']:.2f}", "Rs/Kg"],
    ]
    
    t1 = Table(common_table_data, colWidths=[250, 100, 100])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(t1)
    elements.append(Spacer(1, 15))

    # --- Section 2: Component Details ---
    elements.append(Paragraph("2. Component Specific Stack Costs", header_style))
    
    for comp in components_data:
        elements.append(Paragraph(f"Component: {comp['name']}", styles['Heading3']))
        
        comp_rows = [
            ["Description", "Value", "Unit"],
            ["Stack Height", f"{comp['stack_height']:.2f}", "mm"],
            ["Sheet Thickness", f"{comp['sheet_thickness']:.2f}", "mm"],
            ["Laminations per Stack", f"{comp['lams_per_stack']:.2f}", "Nos"],
            ["Single Lamination Weight", f"{comp['single_lam_weight_g']:.3f}", "grams"],
            ["Total Stack Weight", f"{comp['stack_weight_g']:.2f}", "grams"],
            ["Base Cost (Weight * Cost/Kg)", f"{comp['base_stack_cost']:.2f}", "Rs"],
            ["Riveting Cost", f"{comp['rivet_total_cost']:.2f}", "Rs"],
            ["Pressing Cost", f"{comp['pressing_cost']:.2f}", "Rs"],
            ["Tool Maintenance", f"{comp['tool_maint_cost']:.2f}", "Rs"],
            ["Packing & Transport", f"{comp['packing_cost'] + comp['transport_cost']:.2f}", "Rs"],
            ["FINAL STACK COST", f"{comp['final_stack_cost']:.2f}", "Rs"],
        ]
        
        t_comp = Table(comp_rows, colWidths=[250, 100, 100])
        t_comp.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        elements.append(t_comp)
        elements.append(Spacer(1, 12))

    doc.build(elements)
    buffer.seek(0)
    return buffer

def create_summary_pdf(common_data, components_data, common_inputs):
    """Generates the simplified report (Summary only)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=1, fontSize=16, spaceAfter=12)
    
    # --- Title ---
    elements.append(Paragraph("Sai Precision Tool Industries", title_style))
    elements.append(Spacer(1, 12))

    # --- Table Construction ---
    # Header
    table_data = [
        ["S. No.", "Description", "Value", "Unit"]
    ]
    
    # 1. Common Rates
    table_data.extend([
        ["1", "Yield", f"{common_inputs['yield_pct']:.2f}", "%"],
        ["2", "Raw Material Rate (per Kg)", f"{common_inputs['rm_rate']:.2f}", "Rupees/Kg"],
        ["3", "Scrap Rate (per Kg)", f"{common_inputs['scrap_rate']:.2f}", "Rupees/Kg"],
        ["4", "Net Material Cost per Kg (NRM)", f"{common_data['nrm']:.2f}", "Rupees/Kg"],
        ["5", "Cost per Kg of Lamination (Mfg)", f"{common_data['total_cost_per_kg']:.2f}", "Rupees/Kg"],
    ])
    
    # 2. Components
    counter = 6
    for comp in components_data:
        # Spacer / Header row for Component
        table_data.append(["", f"COMPONENT: {comp['name']}", "", ""])
        
        table_data.extend([
            [f"{counter}", "Stack Height", f"{comp['stack_height']:.2f}", "mm"],
            [f"{counter+1}", "Sheet Thickness", f"{comp['sheet_thickness']:.2f}", "mm"],
            [f"{counter+2}", "Number of Lamination per Stack", f"{comp['lams_per_stack']:.2f}", "Nos"],
            [f"{counter+3}", "Weight of Single Lamination", f"{comp['single_lam_weight_g']:.3f}", "Grams"],
            [f"{counter+4}", "Weight of Lamination per Stack", f"{comp['stack_weight_g']:.2f}", "Grams"],
            [f"{counter+5}", "Total Cost (Including All Charges)", f"{comp['final_stack_cost']:.2f}", "Rupees"],
        ])
        counter += 6

    # Styling
    t = Table(table_data, colWidths=[40, 260, 100, 80])
    
    style_list = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FontSize', (0, 0), (-1, -1), 10),
    ]
    
    # Highlight Component Headers
    row_idx = 0
    for row in table_data:
        if "COMPONENT:" in row[1]:
            style_list.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.lightgrey))
            style_list.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
        row_idx += 1

    t.setStyle(TableStyle(style_list))
    elements.append(t)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==========================================
# 3. Main Streamlit App
# ==========================================
def main():
    st.set_page_config(page_title="Multi-Component Costing V7", layout="wide")
    st.title("🏭 Multi-Component Costing Calculator V7")
    
    if 'components' not in st.session_state:
        st.session_state.components = [{'id': 0, 'name': 'Stator'}]

    def add_component():
        new_id = len(st.session_state.components)
        st.session_state.components.append({'id': new_id, 'name': f'Component {new_id + 1}'})

    def remove_component(idx):
        if len(st.session_state.components) > 1:
            st.session_state.components.pop(idx)

    # ==========================
    # SIDEBAR: RATES & OVERHEADS
    # ==========================
    with st.sidebar:
        st.header("1. Global Rates")
        rm_rate = st.number_input("Raw Material (Rs/Kg)", value=92.0)
        scrap_rate = st.number_input("Scrap Rate (Rs/Kg)", value=32.0)
        stroke_rate = st.number_input("Stroke Rate (Rs/Stroke)", value=0.50)
        packing_rate = st.number_input("Packing Cost (Rs/Kg)", value=2.0)
        transport_rate = st.number_input("Transport Cost (Rs/Kg)", value=3.0)

        st.header("2. Overheads (%)")
        inventory_pct = st.number_input("Inventory (on NRM)", value=2.0)
        rejection_pct = st.number_input("Rejection (on NRM)", value=2.0)
        overhead_pct = st.number_input("Overhead (on Process)", value=20.0)
        profit_pct = st.number_input("Profit (on NRM)", value=12.0)

    # ==========================
    # MAIN: TOOL & COMPONENT INPUTS
    # ==========================
    
    st.subheader("🛠️ Tool & Strip Parameters (Common)")
    
    c1, c2, c3 = st.columns(3)
    tool_ref_name = c1.text_input("Tool Reference / Name", "AL-102517A Combo")
    yield_pct = c2.number_input("Overall Yield (%)", value=31.97)
    weight_per_stroke_g = c3.number_input("Total Weight per Stroke (g)", value=25.0, help="Sum of weights of all parts produced in 1 stroke")

    # Calculate Common Costs
    common_inputs = {
        'tool_ref_name': tool_ref_name, 'yield_pct': yield_pct, 'weight_per_stroke_g': weight_per_stroke_g,
        'rm_rate': rm_rate, 'scrap_rate': scrap_rate, 'stroke_rate': stroke_rate,
        'inventory_pct': inventory_pct, 'rejection_pct': rejection_pct,
        'overhead_pct': overhead_pct, 'profit_pct': profit_pct
    }
    common_data = calculate_common_rates(common_inputs)

    col_a, col_b = st.columns(2)
    col_a.metric("Base Manufacturing Cost per Kg", f"₹ {common_data['total_cost_per_kg']:.2f}")
    col_b.metric("Strokes per Kg (Rounded Up)", f"{common_data['strokes_per_kg']}")
    st.divider()

    # --- Part 2: Components List ---
    st.subheader("📦 Components Config")
    
    all_components_data = []

    for idx, comp in enumerate(st.session_state.components):
        with st.expander(f"Component #{idx+1}: {comp.get('name', 'New')}", expanded=True):
            col_a, col_b, col_c = st.columns([1, 1, 1])
            
            # Column A: Basics
            c_name = col_a.text_input("Component Name", value=comp.get('name', 'Part'), key=f"name_{idx}")
            
            # Column B: Stack Dimensions
            c_height = col_b.number_input("Stack Height (mm)", value=33.0, key=f"ht_{idx}")
            c_thick = col_b.number_input("Sheet Thickness (mm)", value=0.5, key=f"th_{idx}")
            c_weight = col_b.number_input("Single Lam Weight (g)", value=13.14, key=f"wt_{idx}")
            
            # Auto-calculate lams for default tool maint logic
            lams_est = c_height / c_thick if c_thick > 0 else 0
            auto_maint_cost = 0.03 * lams_est

            # Column C: Fixed Costs
            c_rivet_cost = col_c.number_input("Cost/Rivet (Rs)", value=0.25, key=f"rc_{idx}")
            c_rivet_cnt = col_c.number_input("No. of Rivets", value=0, key=f"rn_{idx}")
            c_rivet_man = col_c.number_input("Riveting Manpower (Rs)", value=0.7, key=f"rm_{idx}")
            c_press = col_c.number_input("Pressing Cost (Rs)", value=1.0, key=f"pr_{idx}")
            
            # Tool Maintenance Override Logic
            st.markdown("---")
            m_col1, m_col2 = st.columns([1, 2])
            override_maint = m_col1.checkbox("Manual Tool Maint?", key=f"ovr_{idx}")
            
            if override_maint:
                c_tool_maint = m_col2.number_input("Enter Maint. Cost (Rs)", value=float(f"{auto_maint_cost:.2f}"), key=f"tm_man_{idx}")
            else:
                m_col2.info(f"Auto Tool Maint (0.03 * {lams_est:.1f} Lams): **₹ {auto_maint_cost:.2f}**")
                c_tool_maint = auto_maint_cost

            # Delete Button
            if idx > 0:
                if st.button("🗑️ Remove Component", key=f"del_{idx}"):
                    remove_component(idx)
                    st.rerun()

            # Calculate Component Cost
            comp_inputs = {
                'name': c_name, 'stack_height': c_height, 'sheet_thickness': c_thick,
                'single_lam_weight_g': c_weight, 'rivet_unit_cost': c_rivet_cost,
                'rivet_count': c_rivet_cnt, 'rivet_manpower_cost': c_rivet_man,
                'pressing_cost': c_press,
                'tool_maint_cost': c_tool_maint
            }
            comp_result = calculate_component_cost(common_data, comp_inputs, packing_rate, transport_rate)
            all_components_data.append(comp_result)

            # Mini Result Display
            st.markdown(f"""
            **Stack Weight:** {comp_result['stack_weight_g']:.2f} g | 
            **Landed Cost:** <span style="color:green; font-weight:bold; font-size:1.2em">₹ {comp_result['final_stack_cost']:.2f}</span>
            """, unsafe_allow_html=True)

    st.button("➕ Add Another Component", on_click=add_component)

    st.divider()
    
    # ==========================
    # DISPLAY FULL REPORT PREVIEW
    # ==========================
    st.subheader("📋 Report Preview")
    
    # 1. Common Rates Table
    st.markdown("#### 1. Common Manufacturing Cost per Kg")
    df_common = pd.DataFrame([
        {"Parameter": "Yield (%)", "Value": common_inputs['yield_pct']},
        {"Parameter": "Raw Material Rate (Rs/Kg)", "Value": common_inputs['rm_rate']},
        {"Parameter": "Scrap Rate (Rs/Kg)", "Value": common_inputs['scrap_rate']},
        {"Parameter": "Net Material Cost - NRM (Rs/Kg)", "Value": common_data['nrm']},
        {"Parameter": "Processing Cost (Rs/Kg)", "Value": common_data['process_cost']},
        {"Parameter": "Overheads + Profit (Rs/Kg)", "Value": common_data['inventory_cost'] + common_data['rejection_cost'] + common_data['overhead_cost'] + common_data['profit_cost']},
        {"Parameter": "TOTAL MFG COST PER KG", "Value": common_data['total_cost_per_kg']},
    ])
    st.table(df_common.style.format({"Value": "{:.2f}"}))
    
    # 2. Component Details Tables
    st.markdown("#### 2. Component Details")
    for comp in all_components_data:
        st.markdown(f"**Component: {comp['name']}**")
        df_comp = pd.DataFrame([
            {"Parameter": "Stack Height (mm)", "Value": comp['stack_height']},
            {"Parameter": "Laminations (Nos)", "Value": comp['lams_per_stack']},
            {"Parameter": "Weight of Stack (g)", "Value": comp['stack_weight_g']},
            {"Parameter": "Base Cost (Rs)", "Value": comp['base_stack_cost']},
            {"Parameter": "Riveting + Pressing (Rs)", "Value": comp['rivet_total_cost'] + comp['pressing_cost']},
            {"Parameter": "Tool Maintenance (Rs)", "Value": comp['tool_maint_cost']},
            {"Parameter": "Packing + Transport (Rs)", "Value": comp['packing_cost'] + comp['transport_cost']},
            {"Parameter": "FINAL LANDED COST (Rs)", "Value": comp['final_stack_cost']},
        ])
        st.table(df_comp.style.format({"Value": "{:.2f}"}))

    # ==========================
    # DOWNLOAD BUTTONS
    # ==========================
    st.divider()
    st.subheader("💾 Download Options")
    
    d_col1, d_col2 = st.columns(2)
    
    # Button 1: Detailed
    detailed_pdf = create_detailed_pdf(common_data, all_components_data, common_inputs)
    d_col1.download_button(
        label="📄 Download Detailed Report (Full Breakdown)",
        data=detailed_pdf,
        file_name=f"{tool_ref_name}_Detailed_Costing.pdf",
        mime="application/pdf"
    )
    
    # Button 2: Summary
    summary_pdf = create_summary_pdf(common_data, all_components_data, common_inputs)
    d_col2.download_button(
        label="📑 Download Summary Report (Less Details)",
        data=summary_pdf,
        file_name=f"{tool_ref_name}_Summary_Costing.pdf",
        mime="application/pdf"
    )

if __name__ == "__main__":
    main()