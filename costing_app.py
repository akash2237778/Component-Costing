import streamlit as st
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import io
import math
import json
import os
from datetime import datetime
from PIL import Image as PILImage

# ==========================================
# 0. Configuration & Defaults
# ==========================================
HISTORY_FILE = 'costing_history.json'
LOGO_FILE = 'logo.png' 

# SYSTEM DEFAULTS (Used for Highlighting)
DEFAULTS = {
    'rm_rate': 92.0,
    'scrap_rate': 32.0,
    'stroke_rate': 0.50,
    'packing_rate': 2.0,
    'transport_rate': 3.0,
    'yield_pct': 31.97,
    'weight_per_stroke_g': 25.0,
    'sheet_thickness': 0.5,
    'tool_ref_name': "AL-102517A Combo",
    'inventory_pct': 2.0,
    'rejection_pct': 2.0,
    'overhead_pct': 20.0,
    'profit_pct': 12.0,
    # Component Defaults
    'comp_stack_height': 33.0,
    'comp_weight': 13.14,
    'comp_rivet_cost': 0.25,
    'comp_rivet_count': 0,
    'comp_rivet_man': 0.7,
    'comp_press': 1.0,
    'comp_name': "New Component"
}

# ==========================================
# 1. Helper Functions
# ==========================================

def load_history_file():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_history_file(history_data):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history_data, f, indent=4)

def save_current_state(common_inputs, components_state_list):
    history = load_history_file()
    entry = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tool_name": common_inputs['tool_ref_name'],
        "common_inputs": common_inputs,
        "components_data": components_state_list
    }
    history.insert(0, entry)
    save_history_file(history)
    return entry

def delete_history_entry(entry_id):
    history = load_history_file()
    history = [h for h in history if h['id'] != entry_id]
    save_history_file(history)

# --- UI HIGHLIGHTER HELPER (UPDATED TO SMALL DIAMOND) ---
def lbl(label, key, default_ref_key=None, custom_default=None):
    """
    Checks if the current session state value matches the system default.
    If yes, appends a Small Blue Diamond (🔹).
    """
    target_val = custom_default if custom_default is not None else DEFAULTS.get(default_ref_key)
    current_val = st.session_state.get(key)
    
    if current_val is None:
        current_val = target_val

    is_default = False
    try:
        if isinstance(target_val, float):
            is_default = math.isclose(float(current_val), target_val, rel_tol=1e-9)
        else:
            is_default = (current_val == target_val)
    except:
        is_default = (current_val == target_val)

    # UPDATED ICON HERE
    if is_default:
        return f"{label} 🔹"
    return label

# ==========================================
# 2. Calculation Logic
# ==========================================

def calculate_common_rates(inputs):
    data = {}
    try:
        data['yield_pct'] = inputs['yield_pct']
        data['gross_weight'] = 1 / (inputs['yield_pct'] / 100) if inputs['yield_pct'] > 0 else 0
        data['net_weight'] = 1.0 
        data['scrap_weight'] = data['gross_weight'] - 1.0
        
        data['rm_rate'] = inputs['rm_rate']
        data['rm_cost'] = data['gross_weight'] * data['rm_rate']
        
        data['scrap_rate'] = inputs['scrap_rate']
        data['scrap_recovery'] = data['scrap_weight'] * data['scrap_rate']
        
        data['nrm'] = data['rm_cost'] - data['scrap_recovery']
    except ZeroDivisionError:
        data.update({'gross_weight':0, 'scrap_weight':0, 'rm_cost':0, 'scrap_recovery':0, 'nrm':0})

    try:
        if inputs['weight_per_stroke_g'] > 0:
            raw_strokes = 1000 / inputs['weight_per_stroke_g']
            data['strokes_per_kg'] = math.ceil(raw_strokes)
        else:
            data['strokes_per_kg'] = 0
            
        data['stroke_rate'] = inputs['stroke_rate']
        data['process_cost'] = data['strokes_per_kg'] * data['stroke_rate']
    except:
        data['process_cost'] = 0

    data['inventory_cost'] = data['nrm'] * (inputs['inventory_pct'] / 100)
    data['rejection_cost'] = data['nrm'] * (inputs['rejection_pct'] / 100)
    data['overhead_cost'] = data['process_cost'] * (inputs['overhead_pct'] / 100)
    data['profit_cost'] = data['nrm'] * (inputs['profit_pct'] / 100)

    data['total_cost_per_kg'] = (
        data['nrm'] + 
        data['process_cost'] + 
        data['inventory_cost'] + 
        data['rejection_cost'] + 
        data['overhead_cost'] + 
        data['profit_cost']
    )
    return data

def calculate_component_cost(common_data, comp_input, packing_rate, transport_rate, global_sheet_thickness):
    c_data = comp_input.copy()
    c_data['sheet_thickness'] = global_sheet_thickness

    if c_data['sheet_thickness'] > 0:
        c_data['lams_per_stack'] = c_data['stack_height'] / c_data['sheet_thickness']
    else:
        c_data['lams_per_stack'] = 0
        
    c_data['stack_weight_g'] = c_data['lams_per_stack'] * c_data['single_lam_weight_g']
    c_data['stack_weight_kg'] = c_data['stack_weight_g'] / 1000
    c_data['base_stack_cost'] = c_data['stack_weight_kg'] * common_data['total_cost_per_kg']
    
    rivet_mat_cost = c_data['rivet_unit_cost'] * c_data['rivet_count']
    c_data['rivet_total_cost'] = rivet_mat_cost + c_data['rivet_manpower_cost']
    
    if c_data.get('tool_maint_cost_is_manual', False):
        pass 
    else:
         c_data['tool_maint_cost'] = 0.03 * c_data['lams_per_stack']

    c_data['stack_mfg_cost'] = (
        c_data['base_stack_cost'] + 
        c_data['rivet_total_cost'] + 
        c_data['pressing_cost'] + 
        c_data['tool_maint_cost']
    )
    
    c_data['packing_cost'] = c_data['stack_weight_kg'] * packing_rate
    c_data['transport_cost'] = c_data['stack_weight_kg'] * transport_rate
    c_data['final_stack_cost'] = c_data['stack_mfg_cost'] + c_data['packing_cost'] + c_data['transport_cost']
    
    return c_data

# ==========================================
# 2. PDF Generation
# ==========================================

def get_header_elements(title_text):
    elements = []
    if os.path.exists(LOGO_FILE):
        try:
            pil_img = PILImage.open(LOGO_FILE)
            orig_w, orig_h = pil_img.size
            aspect = orig_h / float(orig_w)
            target_w = 2.0 * inch
            target_h = target_w * aspect
            if target_h > 1.2 * inch:
                target_h = 1.2 * inch
                target_w = target_h / aspect
            im = Image(LOGO_FILE, width=target_w, height=target_h)
            im.hAlign = 'LEFT'
            elements.append(im)
            elements.append(Spacer(1, 12))
        except: pass 

    styles = getSampleStyleSheet()
    company_style = ParagraphStyle('Company', parent=styles['Heading1'], alignment=TA_LEFT, fontSize=14, textColor=colors.black, spaceAfter=6)
    elements.append(Paragraph("Sai Precision Tool Industries", company_style))
    report_title_style = ParagraphStyle('ReportTitle', parent=styles['Normal'], alignment=TA_LEFT, fontSize=12, textColor=colors.black, spaceAfter=20)
    elements.append(Paragraph(title_text, report_title_style))
    return elements

def on_page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    date_str = datetime.now().strftime("%d-%b-%Y %H:%M")
    canvas.drawString(30, 20, f"Generated on: {date_str}")
    canvas.drawRightString(A4[0]-30, 20, f"Page {doc.page}")
    canvas.restoreState()

def create_detailed_pdf(common_data, components_data, common_inputs):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=40)
    
    elements = get_header_elements(f"Detailed Costing Report: {common_inputs['tool_ref_name']}")
    styles = getSampleStyleSheet()
    
    pro_table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.black),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white]),
    ])

    # 1. Common Rates
    elements.append(Paragraph("1. Common Manufacturing Parameters", styles['Heading2']))
    
    common_table_data = [
        ["Parameter", "Value", "Unit"],
        ["Yield", f"{common_inputs['yield_pct']:.2f}", "%"],
        ["Sheet Thickness (Common)", f"{common_inputs['sheet_thickness']:.2f}", "mm"],
        ["Raw Material Rate", f"{common_inputs['rm_rate']:.2f}", "Rs/Kg"],
        ["Scrap Rate", f"{common_inputs['scrap_rate']:.2f}", "Rs/Kg"],
        ["Net Material Cost (NRM)", f"{common_data['nrm']:.2f}", "Rs/Kg"],
        ["Strokes per Kg", f"{common_data['strokes_per_kg']}", "Nos"],
        ["Processing Cost", f"{common_data['process_cost']:.2f}", "Rs/Kg"],
        ["Inventory Cost", f"{common_data['inventory_cost']:.2f}", "Rs/Kg"],
        ["Rejection Cost", f"{common_data['rejection_cost']:.2f}", "Rs/Kg"],
        ["Overhead Cost", f"{common_data['overhead_cost']:.2f}", "Rs/Kg"],
        ["Profit", f"{common_data['profit_cost']:.2f}", "Rs/Kg"],
        ["TOTAL MFG COST PER KG", f"{common_data['total_cost_per_kg']:.2f}", "Rs/Kg"],
    ]
    t1 = Table(common_table_data, colWidths=[300, 120, 100])
    t1.setStyle(pro_table_style)
    t1.setStyle(TableStyle([
         ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), 
         ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
         ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
    ]))
    elements.append(t1)
    elements.append(Spacer(1, 20))

    # 2. Components
    elements.append(Paragraph("2. Component Stack Costs", styles['Heading2']))
    
    for comp in components_data:
        elements.append(Paragraph(f"Component: {comp['name']}", styles['Heading3']))
        comp_rows = [
            ["Description", "Value", "Unit"],
            ["Stack Height", f"{comp['stack_height']:.2f}", "mm"],
            ["Sheet Thickness (Ref)", f"{comp['sheet_thickness']:.2f}", "mm"],
            ["Laminations per Stack", f"{comp['lams_per_stack']:.2f}", "Nos"],
            ["Weight of Stack", f"{comp['stack_weight_g']:.2f}", "grams"],
            ["Base Cost (Mat + Process)", f"{comp['base_stack_cost']:.2f}", "Rs"],
            ["Riveting Cost", f"{comp['rivet_total_cost']:.2f}", "Rs"],
            ["Pressing Cost", f"{comp['pressing_cost']:.2f}", "Rs"],
            ["Tool Maintenance", f"{comp['tool_maint_cost']:.2f}", "Rs"],
            ["Packing & Transport", f"{comp['packing_cost'] + comp['transport_cost']:.2f}", "Rs"],
            ["FINAL STACK COST", f"{comp['final_stack_cost']:.2f}", "Rs"],
        ]
        t_comp = Table(comp_rows, colWidths=[300, 120, 100])
        t_comp.setStyle(pro_table_style)
        t_comp.setStyle(TableStyle([('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold')]))
        elements.append(t_comp)
        elements.append(Spacer(1, 15))

    doc.build(elements, onFirstPage=on_page_footer, onLaterPages=on_page_footer)
    buffer.seek(0)
    return buffer

def create_summary_pdf(common_data, components_data, common_inputs):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=40)
    elements = get_header_elements(f"Cost Summary: {common_inputs['tool_ref_name']}")
    
    table_data = [["S. No.", "Description", "Value", "Unit"]]
    
    table_data.extend([
        ["1", "Yield", f"{common_inputs['yield_pct']:.2f}", "%"],
        ["2", "Raw Material Rate", f"{common_inputs['rm_rate']:.2f}", "Rs/Kg"],
        ["3", "Scrap Rate", f"{common_inputs['scrap_rate']:.2f}", "Rs/Kg"],
        ["4", "Net Material Cost (NRM)", f"{common_data['nrm']:.2f}", "Rs/Kg"],
        ["5", "Mfg Cost per Kg", f"{common_data['total_cost_per_kg']:.2f}", "Rs/Kg"],
    ])
    
    counter = 6
    row_styles = []
    
    for comp in components_data:
        table_data.append(["", f"COMPONENT: {comp['name']}", "", ""])
        header_row_idx = len(table_data) - 1
        row_styles.extend([
            ('BACKGROUND', (0, header_row_idx), (-1, header_row_idx), colors.lightgrey),
            ('FONTNAME', (0, header_row_idx), (-1, header_row_idx), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, header_row_idx), (-1, header_row_idx), colors.black),
        ])
        
        table_data.extend([
            [f"{counter}", "Stack Height", f"{comp['stack_height']:.2f}", "mm"],
            [f"{counter+1}", "Sheet Thickness", f"{comp['sheet_thickness']:.2f}", "mm"],
            [f"{counter+2}", "Laminations/Stack", f"{comp['lams_per_stack']:.2f}", "Nos"],
            [f"{counter+3}", "Single Lam Weight", f"{comp['single_lam_weight_g']:.3f}", "g"],
            [f"{counter+4}", "Stack Weight", f"{comp['stack_weight_g']:.2f}", "g"],
            [f"{counter+5}", "Total Cost (Landed)", f"{comp['final_stack_cost']:.2f}", "Rs"],
        ])
        total_row_idx = len(table_data) - 1
        row_styles.append(('FONTNAME', (0, total_row_idx), (-1, total_row_idx), 'Helvetica-Bold'))
        counter += 6

    t = Table(table_data, colWidths=[40, 300, 100, 80])
    base_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.black),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
    ]
    t.setStyle(TableStyle(base_style + row_styles))
    elements.append(t)
    doc.build(elements, onFirstPage=on_page_footer, onLaterPages=on_page_footer)
    buffer.seek(0)
    return buffer

# ==========================================
# 3. Main Streamlit App
# ==========================================
def main():
    st.set_page_config(page_title="Component Cost Calculator", layout="wide", page_icon="🔹")
    
    col_h1, col_h2 = st.columns([1, 5])
    with col_h1:
        if os.path.exists(LOGO_FILE):
            st.image(LOGO_FILE, width=150)
    with col_h2:
        st.title("Component Cost Calculator")
        st.caption("Fields marked with 🔹 are currently set to System Defaults.")

    if 'components' not in st.session_state:
        st.session_state.components = [{'id': 0, 'name': 'Stator'}]

    # Load Data Handler
    if 'loaded_data' in st.session_state:
        ld = st.session_state['loaded_data']
        for k, v in ld['common_inputs'].items():
            st.session_state[k] = v 
        
        st.session_state.components = [] 
        for idx, comp_data in enumerate(ld['components_data']):
            st.session_state.components.append({'id': idx, 'name': comp_data['name']})
            st.session_state[f"name_{idx}"] = comp_data['name']
            st.session_state[f"ht_{idx}"] = comp_data['stack_height']
            st.session_state[f"wt_{idx}"] = comp_data['single_lam_weight_g']
            st.session_state[f"rc_{idx}"] = comp_data.get('rivet_unit_cost', 0.25)
            st.session_state[f"rn_{idx}"] = int(comp_data.get('rivet_count', 0))
            st.session_state[f"rm_{idx}"] = comp_data.get('rivet_manpower_cost', 0.7)
            st.session_state[f"pr_{idx}"] = comp_data.get('pressing_cost', 1.0)
            is_manual = comp_data.get('tool_maint_cost_is_manual', False)
            st.session_state[f"ovr_{idx}"] = is_manual
            if is_manual:
                st.session_state[f"tm_man_{idx}"] = comp_data.get('tool_maint_cost', 0.0)
        del st.session_state['loaded_data']

    def init_key(k, default):
        if k not in st.session_state:
            st.session_state[k] = default

    # Init Global Keys
    init_key('rm_rate', DEFAULTS['rm_rate'])
    init_key('scrap_rate', DEFAULTS['scrap_rate'])
    init_key('stroke_rate', DEFAULTS['stroke_rate'])
    init_key('packing_rate', DEFAULTS['packing_rate'])
    init_key('transport_rate', DEFAULTS['transport_rate'])
    init_key('inventory_pct', DEFAULTS['inventory_pct'])
    init_key('rejection_pct', DEFAULTS['rejection_pct'])
    init_key('overhead_pct', DEFAULTS['overhead_pct'])
    init_key('profit_pct', DEFAULTS['profit_pct'])
    init_key('tool_ref_name', DEFAULTS['tool_ref_name'])
    init_key('yield_pct', DEFAULTS['yield_pct'])
    init_key('weight_per_stroke_g', DEFAULTS['weight_per_stroke_g'])
    init_key('sheet_thickness', DEFAULTS['sheet_thickness'])

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("📜 History")
        history_list = load_history_file()
        if history_list:
            for item in history_list:
                with st.expander(f"{item['timestamp']} - {item['tool_name']}"):
                    if st.button("📂 Load", key=f"load_{item['id']}"):
                        st.session_state['loaded_data'] = item
                        st.rerun()
                    if st.button("🗑️ Delete", key=f"del_hist_{item['id']}"):
                        delete_history_entry(item['id'])
                        st.rerun()
        
        st.divider()
        st.subheader("Global Rates")
        rm_rate = st.number_input(lbl("RM Rate", 'rm_rate', 'rm_rate'), key='rm_rate')
        scrap_rate = st.number_input(lbl("Scrap Rate", 'scrap_rate', 'scrap_rate'), key='scrap_rate')
        stroke_rate = st.number_input(lbl("Stroke Rate", 'stroke_rate', 'stroke_rate'), key='stroke_rate')
        packing_rate = st.number_input(lbl("Packing Cost", 'packing_rate', 'packing_rate'), key='packing_rate')
        transport_rate = st.number_input(lbl("Transport Cost", 'transport_rate', 'transport_rate'), key='transport_rate')

        st.subheader("Overheads (%)")
        inventory_pct = st.number_input(lbl("Inventory", 'inventory_pct', 'inventory_pct'), key='inventory_pct')
        rejection_pct = st.number_input(lbl("Rejection", 'rejection_pct', 'rejection_pct'), key='rejection_pct')
        overhead_pct = st.number_input(lbl("Overhead", 'overhead_pct', 'overhead_pct'), key='overhead_pct')
        profit_pct = st.number_input(lbl("Profit", 'profit_pct', 'profit_pct'), key='profit_pct')

    # --- COMMON INPUTS ---
    with st.container():
        st.info("🛠️ **Tool & Strip Parameters (Common for all Components)**")
        c1, c2, c3, c4 = st.columns(4)
        tool_ref_name = c1.text_input(lbl("Tool Name", 'tool_ref_name', 'tool_ref_name'), key='tool_ref_name')
        yield_pct = c2.number_input(lbl("Yield (%)", 'yield_pct', 'yield_pct'), key='yield_pct')
        weight_per_stroke_g = c3.number_input(lbl("Wt/Stroke (g)", 'weight_per_stroke_g', 'weight_per_stroke_g'), key='weight_per_stroke_g')
        sheet_thickness = c4.number_input(lbl("Sheet Thickness (mm)", 'sheet_thickness', 'sheet_thickness'), key='sheet_thickness')

    common_inputs = {
        'tool_ref_name': tool_ref_name, 'yield_pct': yield_pct, 'weight_per_stroke_g': weight_per_stroke_g,
        'sheet_thickness': sheet_thickness,
        'rm_rate': rm_rate, 'scrap_rate': scrap_rate, 'stroke_rate': stroke_rate,
        'packing_rate': packing_rate, 'transport_rate': transport_rate,
        'inventory_pct': inventory_pct, 'rejection_pct': rejection_pct,
        'overhead_pct': overhead_pct, 'profit_pct': profit_pct
    }
    common_data = calculate_common_rates(common_inputs)

    m1, m2 = st.columns(2)
    m1.metric("Base Mfg Cost / Kg", f"₹ {common_data['total_cost_per_kg']:.2f}", help="Includes Material, Process & Overheads")
    m2.metric("Strokes / Kg", f"{common_data['strokes_per_kg']}")
    st.divider()

    # --- COMPONENTS ---
    st.subheader("📦 Components Config")
    all_components_data = []
    
    for idx, comp in enumerate(st.session_state.components):
        # Init Component Keys
        init_key(f"name_{idx}", comp.get('name', 'Part'))
        init_key(f"ht_{idx}", DEFAULTS['comp_stack_height'])
        init_key(f"wt_{idx}", DEFAULTS['comp_weight'])
        init_key(f"rc_{idx}", DEFAULTS['comp_rivet_cost'])
        init_key(f"rn_{idx}", DEFAULTS['comp_rivet_count'])
        init_key(f"rm_{idx}", DEFAULTS['comp_rivet_man'])
        init_key(f"pr_{idx}", DEFAULTS['comp_press'])
        init_key(f"ovr_{idx}", False)

        with st.expander(f"Component #{idx+1}: {st.session_state[f'name_{idx}']}", expanded=True):
            col_a, col_b, col_c = st.columns([1, 1, 1])
            
            c_name = col_a.text_input(lbl("Component Name", f"name_{idx}", custom_default=f"Component {idx+1}"), key=f"name_{idx}")
            
            c_height = col_b.number_input(lbl("Stack Height", f"ht_{idx}", 'comp_stack_height'), key=f"ht_{idx}")
            col_b.caption(f"Sheet Thick: {sheet_thickness} mm (Common)") 
            
            c_weight = col_b.number_input(lbl("Single Lam Weight (g)", f"wt_{idx}", 'comp_weight'), key=f"wt_{idx}")
            
            lams_est = c_height / sheet_thickness if sheet_thickness > 0 else 0
            auto_maint_cost = 0.03 * lams_est

            c_rivet_cost = col_c.number_input(lbl("Cost/Rivet (Rs)", f"rc_{idx}", 'comp_rivet_cost'), key=f"rc_{idx}")
            c_rivet_cnt = col_c.number_input(lbl("No. of Rivets", f"rn_{idx}", 'comp_rivet_count'), min_value=0, step=1, format="%d", key=f"rn_{idx}")
            c_rivet_man = col_c.number_input(lbl("Riveting Manpower", f"rm_{idx}", 'comp_rivet_man'), key=f"rm_{idx}")
            c_press = col_c.number_input(lbl("Pressing Cost", f"pr_{idx}", 'comp_press'), key=f"pr_{idx}")
            
            st.markdown("---")
            m_col1, m_col2 = st.columns([1, 2])
            override_maint = m_col1.checkbox("Manual Tool Maint?", key=f"ovr_{idx}")
            if override_maint:
                init_key(f"tm_man_{idx}", float(f"{auto_maint_cost:.2f}"))
                c_tool_maint = m_col2.number_input("Enter Maint. Cost", key=f"tm_man_{idx}")
            else:
                m_col2.info(f"Auto Tool Maint: **₹ {auto_maint_cost:.2f}**")
                c_tool_maint = auto_maint_cost

            if idx > 0:
                if st.button("🗑️ Remove", key=f"del_{idx}"):
                    st.session_state.components.pop(idx)
                    st.rerun()

            comp_inputs = {
                'name': c_name, 'stack_height': c_height, 'single_lam_weight_g': c_weight, 
                'rivet_unit_cost': c_rivet_cost, 'rivet_count': c_rivet_cnt, 
                'rivet_manpower_cost': c_rivet_man, 'pressing_cost': c_press,
                'tool_maint_cost': c_tool_maint, 'tool_maint_cost_is_manual': override_maint
            }
            comp_result = calculate_component_cost(common_data, comp_inputs, packing_rate, transport_rate, sheet_thickness)
            all_components_data.append(comp_result)
            
            st.success(f"💰 **Landed Cost per Stack:** ₹ {comp_result['final_stack_cost']:.2f}")

    def add_component():
        new_id = len(st.session_state.components)
        if new_id > 0:
            src_idx = 0
            st.session_state[f"ht_{new_id}"] = st.session_state.get(f"ht_{src_idx}", DEFAULTS['comp_stack_height'])
            st.session_state[f"wt_{new_id}"] = st.session_state.get(f"wt_{src_idx}", DEFAULTS['comp_weight'])
            st.session_state[f"rc_{new_id}"] = st.session_state.get(f"rc_{src_idx}", DEFAULTS['comp_rivet_cost'])
            st.session_state[f"rn_{new_id}"] = st.session_state.get(f"rn_{src_idx}", DEFAULTS['comp_rivet_count'])
            st.session_state[f"rm_{new_id}"] = st.session_state.get(f"rm_{src_idx}", DEFAULTS['comp_rivet_man'])
            st.session_state[f"pr_{new_id}"] = st.session_state.get(f"pr_{src_idx}", DEFAULTS['comp_press'])
        
        st.session_state.components.append({'id': new_id, 'name': f'Component {new_id + 1}'})
    
    st.button("➕ Add Another Component", on_click=add_component)
    st.divider()
    
    # --- ACTIONS ---
    col_act1, col_act2, col_act3 = st.columns(3)
    if col_act1.button("💾 Save Calculation to History"):
        saved_entry = save_current_state(common_inputs, all_components_data)
        st.success(f"Saved: {saved_entry['tool_name']}")
        st.rerun()

    detailed_pdf = create_detailed_pdf(common_data, all_components_data, common_inputs)
    col_act2.download_button("📄 Download Detailed PDF", data=detailed_pdf, file_name=f"{tool_ref_name}_Detailed.pdf", mime="application/pdf")
    
    summary_pdf = create_summary_pdf(common_data, all_components_data, common_inputs)
    col_act3.download_button("📑 Download Summary PDF", data=summary_pdf, file_name=f"{tool_ref_name}_Summary.pdf", mime="application/pdf")

    # --- PREVIEW ---
    st.subheader("📋 Cost Preview")
    if all_components_data:
        df_preview = pd.DataFrame(all_components_data)[['name', 'stack_weight_g', 'base_stack_cost', 'rivet_total_cost', 'tool_maint_cost', 'final_stack_cost']]
        st.table(df_preview.style.format({
            'stack_weight_g': "{:.2f}",
            'base_stack_cost': "{:.2f}",
            'rivet_total_cost': "{:.2f}",
            'tool_maint_cost': "{:.2f}",
            'final_stack_cost': "{:.2f}"
        }))

if __name__ == "__main__":
    main()