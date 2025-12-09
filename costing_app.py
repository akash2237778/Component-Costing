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
# 0. Global Configuration
# ==========================================
COST_HISTORY_FILE = 'costing_history.json'
YIELD_HISTORY_FILE = 'yield_history.json'
LOGO_FILE = 'logo.png' 
PASSWORD = "Akash@123" # CHANGE THIS PASSWORD

# --- Costing Defaults ---
DEFAULTS = {
    'rm_rate': 92.0, 'scrap_rate': 32.0, 'stroke_rate': 0.50,
    'packing_rate': 2.0, 'transport_rate': 3.0,
    'yield_pct': 31.97, 'weight_per_stroke_g': 25.0,
    'sheet_thickness': 0.5, 'tool_ref_name': "AL-102517A Combo",
    'tool_maint_rate': 0.03,
    'inventory_pct': 2.0, 'rejection_pct': 2.0, 'overhead_pct': 20.0, 'profit_pct': 12.0,
    'comp_stack_height': 33.0, 'comp_weight': 13.14,
    'comp_rivet_cost': 0.25, 'comp_rivet_count': 0,
    'comp_rivet_man': 0.7, 'comp_press': 1.0,
    'comp_opt_name': "Extra Process", 'comp_opt_cost': 0.0,
    'comp_name': "New Component"
}

# --- Yield Defaults ---
YIELD_DEFAULTS = {
    'pitch': 50.0, 'sheet_width': 100.0, 'sheet_thickness': 0.5,
    'density': 0.00786, 'yield_deduction': 2.0
}

# ==========================================
# 1. Helper Functions
# ==========================================

def load_history_file(filename):
    if not os.path.exists(filename): return []
    try:
        with open(filename, 'r') as f: return json.load(f)
    except: return []

def save_history_file(filename, history_data):
    with open(filename, 'w') as f: json.dump(history_data, f, indent=4)

# --- Costing Specific Helpers ---
def save_cost_state(common_inputs, components_state_list):
    history = load_history_file(COST_HISTORY_FILE)
    entry = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tool_name": common_inputs['tool_ref_name'],
        "common_inputs": common_inputs,
        "components_data": components_state_list
    }
    history.insert(0, entry)
    save_history_file(COST_HISTORY_FILE, history)
    return entry

def delete_cost_history_entry(entry_id):
    history = load_history_file(COST_HISTORY_FILE)
    history = [h for h in history if h['id'] != entry_id]
    save_history_file(COST_HISTORY_FILE, history)

# --- Yield Specific Helpers ---
def save_yield_state(name, global_inputs, components_list):
    history = load_history_file(YIELD_HISTORY_FILE)
    entry = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "name": name,
        "global_inputs": global_inputs,
        "components": components_list
    }
    history.insert(0, entry)
    save_history_file(YIELD_HISTORY_FILE, history)
    return entry

def delete_yield_history_entry(entry_id):
    history = load_history_file(YIELD_HISTORY_FILE)
    history = [h for h in history if h['id'] != entry_id]
    save_history_file(YIELD_HISTORY_FILE, history)

def lbl(label, key, default_ref_key=None, defaults_dict=DEFAULTS):
    target_val = defaults_dict.get(default_ref_key)
    current_val = st.session_state.get(key)
    if current_val is None: current_val = target_val
    
    is_default = False
    try:
        if isinstance(target_val, float): is_default = math.isclose(float(current_val), target_val, rel_tol=1e-9)
        else: is_default = (current_val == target_val)
    except: is_default = (current_val == target_val)
    
    return f"{label} 🔹" if is_default else label

# ==========================================
# 2. Logic: Cost Calculator
# ==========================================

def calculate_common_rates(inputs):
    data = {}
    try:
        data['yield_pct'] = inputs['yield_pct']
        data['gross_weight'] = 1 / (inputs['yield_pct'] / 100) if inputs['yield_pct'] > 0 else 0
        data['rm_rate'] = inputs['rm_rate']
        data['rm_cost'] = data['gross_weight'] * data['rm_rate']
        data['scrap_rate'] = inputs['scrap_rate']
        data['scrap_weight'] = data['gross_weight'] - 1.0
        data['scrap_recovery'] = data['scrap_weight'] * data['scrap_rate']
        data['nrm'] = data['rm_cost'] - data['scrap_recovery']
    except:
        data.update({'gross_weight':0, 'scrap_weight':0, 'rm_cost':0, 'scrap_recovery':0, 'nrm':0})

    try:
        if inputs['weight_per_stroke_g'] > 0:
            data['strokes_per_kg'] = math.ceil(1000 / inputs['weight_per_stroke_g'])
        else:
            data['strokes_per_kg'] = 0
        data['process_cost'] = data['strokes_per_kg'] * inputs['stroke_rate']
    except:
        data['process_cost'] = 0

    data['inventory_cost'] = data['nrm'] * (inputs['inventory_pct'] / 100)
    data['rejection_cost'] = data['nrm'] * (inputs['rejection_pct'] / 100)
    data['overhead_cost'] = data['process_cost'] * (inputs['overhead_pct'] / 100)
    data['profit_cost'] = data['nrm'] * (inputs['profit_pct'] / 100)

    data['total_cost_per_kg'] = (data['nrm'] + data['process_cost'] + data['inventory_cost'] + 
                                 data['rejection_cost'] + data['overhead_cost'] + data['profit_cost'])
    data['tool_maint_rate'] = inputs['tool_maint_rate']
    return data

def calculate_component_cost(common_data, comp_input, packing_rate, transport_rate, global_sheet_thickness):
    c = comp_input.copy()
    c['sheet_thickness'] = global_sheet_thickness
    c['lams_per_stack'] = c['stack_height'] / c['sheet_thickness'] if c['sheet_thickness'] > 0 else 0
    c['stack_weight_g'] = c['lams_per_stack'] * c['single_lam_weight_g']
    c['stack_weight_kg'] = c['stack_weight_g'] / 1000
    c['base_stack_cost'] = c['stack_weight_kg'] * common_data['total_cost_per_kg']
    
    c['rivet_total_cost'] = (c['rivet_unit_cost'] * c['rivet_count']) + c['rivet_manpower_cost']
    c['tool_maint_cost'] = c['lams_per_stack'] * common_data['tool_maint_rate']
    c['opt_cost'] = c.get('opt_cost', 0.0)
    
    c['stack_mfg_cost'] = c['base_stack_cost'] + c['rivet_total_cost'] + c['pressing_cost'] + c['tool_maint_cost'] + c['opt_cost']
    c['packing_cost'] = c['stack_weight_kg'] * packing_rate
    c['transport_cost'] = c['stack_weight_kg'] * transport_rate
    c['final_stack_cost'] = c['stack_mfg_cost'] + c['packing_cost'] + c['transport_cost']
    
    c['pack_trans_total'] = c['packing_cost'] + c['transport_cost']
    return c

# ==========================================
# 3. PDF Generation
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
        ["Tool Maint Rate (x)", f"{common_inputs['tool_maint_rate']:.2f}", "Rs/Stroke"],
        ["TOTAL MFG COST PER KG", f"{common_data['total_cost_per_kg']:.2f}", "Rs/Kg"],
    ]
    t1 = Table(common_table_data, colWidths=[300, 120, 100])
    t1.setStyle(pro_table_style)
    t1.setStyle(TableStyle([('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey), ('TEXTCOLOR', (0, -1), (-1, -1), colors.black)]))
    elements.append(t1)
    elements.append(Spacer(1, 20))

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
        ]
        if comp['opt_cost'] > 0:
            comp_rows.append([f"{comp['opt_name']} (Optional)", f"{comp['opt_cost']:.2f}", "Rs"])
        comp_rows.extend([
            ["Packing & Transport", f"{comp['packing_cost'] + comp['transport_cost']:.2f}", "Rs"],
            ["FINAL STACK COST", f"{comp['final_stack_cost']:.2f}", "Rs"],
        ])
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
        ])
        if comp['opt_cost'] > 0:
             table_data.append([f"", f"Includes: {comp['opt_name']}", f"{comp['opt_cost']:.2f}", "Rs"])
        table_data.append([f"{counter+5}", "Total Cost (Landed)", f"{comp['final_stack_cost']:.2f}", "Rs"])
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
# 4. Page: Cost Calculator
# ==========================================
def page_cost_calculator():
    st.title("Component Cost Calculator")
    st.caption("Fields marked with 🔹 are currently set to System Defaults.")

    if 'components' not in st.session_state: st.session_state.components = [{'id': 0, 'name': 'Stator'}]

    if 'loaded_data' in st.session_state:
        ld = st.session_state['loaded_data']
        for k, v in ld['common_inputs'].items(): st.session_state[k] = v 
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
            st.session_state[f"on_{idx}"] = comp_data.get('opt_name', DEFAULTS['comp_opt_name'])
            st.session_state[f"oc_{idx}"] = comp_data.get('opt_cost', DEFAULTS['comp_opt_cost'])
        del st.session_state['loaded_data']

    def init_key(k, default):
        if k not in st.session_state: st.session_state[k] = default

    for k in DEFAULTS.keys():
        if k.startswith('comp_'): continue
        init_key(k, DEFAULTS[k])

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("📜 Costing History")
        history_list = load_history_file(COST_HISTORY_FILE)
        if history_list:
            for item in history_list:
                with st.expander(f"{item['timestamp']} - {item['tool_name']}"):
                    if st.button("📂 Load", key=f"load_{item['id']}"):
                        st.session_state['loaded_data'] = item
                        st.rerun()
                    if st.button("🗑️ Delete", key=f"del_hist_{item['id']}"):
                        delete_cost_history_entry(item['id'])
                        st.rerun()
        st.divider()
        st.subheader("Global Rates")
        rm_rate = st.number_input(lbl("RM Rate", 'rm_rate'), key='rm_rate', step=1.0)
        scrap_rate = st.number_input(lbl("Scrap Rate", 'scrap_rate'), key='scrap_rate', step=1.0)
        stroke_rate = st.number_input(lbl("Stroke Rate", 'stroke_rate'), key='stroke_rate', step=0.05, format="%.2f")
        packing_rate = st.number_input(lbl("Packing Cost", 'packing_rate'), key='packing_rate', step=0.5)
        transport_rate = st.number_input(lbl("Transport Cost", 'transport_rate'), key='transport_rate', step=0.5)
        st.subheader("Overheads (%)")
        inventory_pct = st.number_input(lbl("Inventory", 'inventory_pct'), key='inventory_pct', step=0.5)
        rejection_pct = st.number_input(lbl("Rejection", 'rejection_pct'), key='rejection_pct', step=0.5)
        overhead_pct = st.number_input(lbl("Overhead", 'overhead_pct'), key='overhead_pct', step=1.0)
        profit_pct = st.number_input(lbl("Profit", 'profit_pct'), key='profit_pct', step=0.5)

    # --- COMMON INPUTS ---
    with st.container():
        st.info("🛠️ **Tool & Strip Parameters (Common)**")
        with st.expander("Configure Tool Settings", expanded=True):
            c1, c2, c3 = st.columns(3)
            tool_ref_name = c1.text_input(lbl("Tool Name", 'tool_ref_name'), key='tool_ref_name')
            yield_pct = c2.number_input(lbl("Yield (%)", 'yield_pct'), key='yield_pct', step=0.1)
            weight_per_stroke_g = c3.number_input(lbl("Wt/Stroke (g)", 'weight_per_stroke_g'), key='weight_per_stroke_g', step=0.1)
            
            c4, c5, c6 = st.columns(3)
            sheet_thickness = c4.number_input(lbl("Sheet Thickness (mm)", 'sheet_thickness'), key='sheet_thickness', step=0.1)
            tool_maint_rate = c5.number_input(lbl("Tool Maint (Rs/Stroke)", 'tool_maint_rate'), key='tool_maint_rate', format="%.3f", step=0.01)

    common_inputs = {
        'tool_ref_name': tool_ref_name, 'yield_pct': yield_pct, 'weight_per_stroke_g': weight_per_stroke_g,
        'sheet_thickness': sheet_thickness, 'tool_maint_rate': tool_maint_rate,
        'rm_rate': rm_rate, 'scrap_rate': scrap_rate, 'stroke_rate': stroke_rate,
        'packing_rate': packing_rate, 'transport_rate': transport_rate,
        'inventory_pct': inventory_pct, 'rejection_pct': rejection_pct,
        'overhead_pct': overhead_pct, 'profit_pct': profit_pct
    }
    common_data = calculate_common_rates(common_inputs)

    # --- DASHBOARD ---
    st.markdown("### 📊 Cost Analysis")
    with st.container():
        m1, m2, m3 = st.columns([1, 1, 2])
        m1.metric("Base Cost / Kg", f"₹ {common_data['total_cost_per_kg']:.2f}")
        m2.metric("Strokes / Kg", f"{common_data['strokes_per_kg']}")
        
        b_cols = st.columns(5)
        b_cols[0].metric("Process", f"₹{common_data['process_cost']:.1f}")
        b_cols[1].metric("Inv.", f"₹{common_data['inventory_cost']:.1f}")
        b_cols[2].metric("Rej.", f"₹{common_data['rejection_cost']:.1f}")
        b_cols[3].metric("O/H", f"₹{common_data['overhead_cost']:.1f}")
        b_cols[4].metric("Profit", f"₹{common_data['profit_cost']:.1f}")
    st.divider()

    # --- COMPONENTS ---
    st.subheader("📦 Component Configuration")
    all_components_data = []
    
    stack_height_step = max(0.01, float(sheet_thickness))

    for idx, comp in enumerate(st.session_state.components):
        init_key(f"name_{idx}", comp.get('name', 'Part'))
        init_key(f"ht_{idx}", DEFAULTS['comp_stack_height'])
        init_key(f"wt_{idx}", DEFAULTS['comp_weight'])
        init_key(f"rc_{idx}", DEFAULTS['comp_rivet_cost'])
        init_key(f"rn_{idx}", DEFAULTS['comp_rivet_count'])
        init_key(f"rm_{idx}", DEFAULTS['comp_rivet_man'])
        init_key(f"pr_{idx}", DEFAULTS['comp_press'])
        init_key(f"on_{idx}", DEFAULTS['comp_opt_name'])
        init_key(f"oc_{idx}", DEFAULTS['comp_opt_cost'])

        with st.expander(f"Component #{idx+1}: {st.session_state[f'name_{idx}']}", expanded=True):
            # Row 1: Dimensions
            c1, c2, c3 = st.columns(3)
            c_name = c1.text_input(lbl("Component Name", f"name_{idx}", 'comp_name'), key=f"name_{idx}")
            c_height = c2.number_input(lbl("Stack Height (mm)", f"ht_{idx}", 'comp_stack_height'), key=f"ht_{idx}", step=stack_height_step)
            c_weight = c3.number_input(lbl("Single Lam Wt (g)", f"wt_{idx}", 'comp_weight'), key=f"wt_{idx}", step=0.1)
            
            st.divider()
            
            # Row 2: Post-Processing
            r1, r2, r3, r4 = st.columns(4)
            c_rivet_cost = r1.number_input(lbl("Rivet Cost (Rs)", f"rc_{idx}", 'comp_rivet_cost'), key=f"rc_{idx}", step=0.05, format="%.2f")
            c_rivet_cnt = r2.number_input(lbl("Count", f"rn_{idx}", 'comp_rivet_count'), min_value=0, step=1, format="%d", key=f"rn_{idx}")
            c_rivet_man = r3.number_input(lbl("Manpower (Rs)", f"rm_{idx}", 'comp_rivet_man'), key=f"rm_{idx}", step=0.1)
            c_press = r4.number_input(lbl("Pressing (Rs)", f"pr_{idx}", 'comp_press'), key=f"pr_{idx}", step=0.05, format="%.2f")
            
            st.divider()
            
            # Row 3: Extras
            o1, o2, o3 = st.columns([2, 1, 2])
            c_opt_name = o1.text_input(lbl("Optional Cost Name", f"on_{idx}", 'comp_opt_name'), key=f"on_{idx}")
            c_opt_cost = o2.number_input(lbl("Value (Rs)", f"oc_{idx}", 'comp_opt_cost'), key=f"oc_{idx}", step=0.5)
            
            lams_calc = c_height / sheet_thickness if sheet_thickness > 0 else 0
            maint_calc = lams_calc * tool_maint_rate
            o3.info(f"Tool Maint (Auto): **₹ {maint_calc:.2f}**")

            if idx > 0:
                if st.button("🗑️ Remove Component", key=f"del_{idx}"):
                    st.session_state.components.pop(idx)
                    st.rerun()

            comp_inputs = {
                'name': c_name, 'stack_height': c_height, 'single_lam_weight_g': c_weight, 
                'rivet_unit_cost': c_rivet_cost, 'rivet_count': c_rivet_cnt, 
                'rivet_manpower_cost': c_rivet_man, 'pressing_cost': c_press,
                'opt_name': c_opt_name, 'opt_cost': c_opt_cost
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
            st.session_state[f"on_{new_id}"] = st.session_state.get(f"on_{src_idx}", DEFAULTS['comp_opt_name'])
            st.session_state[f"oc_{new_id}"] = st.session_state.get(f"oc_{src_idx}", DEFAULTS['comp_opt_cost'])
        st.session_state.components.append({'id': new_id, 'name': f'Component {new_id + 1}'})
    
    st.button("➕ Add Another Component", on_click=add_component)
    st.divider()
    
    # --- ACTIONS ---
    col_act1, col_act2, col_act3 = st.columns(3)
    if col_act1.button("💾 Save Calculation to History"):
        saved_entry = save_cost_state(common_inputs, all_components_data)
        st.success(f"Saved: {saved_entry['tool_name']}")
        st.rerun()

    detailed_pdf = create_detailed_pdf(common_data, all_components_data, common_inputs)
    col_act2.download_button("📄 Download Detailed PDF", data=detailed_pdf, file_name=f"{tool_ref_name}_Detailed.pdf", mime="application/pdf")
    
    summary_pdf = create_summary_pdf(common_data, all_components_data, common_inputs)
    col_act3.download_button("📑 Download Summary PDF", data=summary_pdf, file_name=f"{tool_ref_name}_Summary.pdf", mime="application/pdf")

    # --- PREVIEW ---
    st.subheader("📋 Full Cost Preview")
    if all_components_data:
        preview_data = []
        for c in all_components_data:
            row = {
                "Component": c['name'],
                "Height (mm)": c['stack_height'],
                "Lams": c['lams_per_stack'],
                "Weight (g)": c['stack_weight_g'],
                "Base Cost": c['base_stack_cost'],
                "Riveting": c['rivet_total_cost'],
                "Pressing": c['pressing_cost'],
                "Tool Maint": c['tool_maint_cost'],
                "Optional": c['opt_cost'],
                "Pack/Trans": c['pack_trans_total'],
                "TOTAL": c['final_stack_cost']
            }
            preview_data.append(row)
        
        df_preview = pd.DataFrame(preview_data)
        format_dict = {
            "Height (mm)": "{:.2f}",
            "Lams": "{:.1f}",
            "Weight (g)": "{:.2f}",
            "Base Cost": "{:.2f}",
            "Riveting": "{:.2f}",
            "Pressing": "{:.2f}",
            "Tool Maint": "{:.2f}",
            "Optional": "{:.2f}",
            "Pack/Trans": "{:.2f}",
            "TOTAL": "{:.2f}"
        }
        st.table(df_preview.style.format(format_dict))

# ==========================================
# 5. Page: Yield Calculator (Fixed Loading)
# ==========================================
def page_yield_calculator():
    st.title("Material Yield Calculator")
    st.caption("Calculation: Finish Area = (Comp1 × Count) + (Comp2 × Count) + ...")

    # --- HISTORY LOADING LOGIC ---
    if 'yield_loaded_data' in st.session_state:
        ld = st.session_state['yield_loaded_data']
        
        # 1. Load Global Inputs (Pitch, Width, etc.)
        for k, v in ld['global_inputs'].items(): 
            st.session_state[k] = v
            
        # 2. Load Calculation Name
        if 'name' in ld:
            st.session_state['y_calc_name'] = ld['name']
            
        # 3. Load Components Data List
        st.session_state.yield_comps = ld['components']
        
        # 4. CRITICAL FIX: Force update widget keys for Components
        # Streamlit widgets hold onto old values unless the specific 'key' in session_state is updated.
        for idx, comp in enumerate(st.session_state.yield_comps):
            # Update Outer Area Key
            st.session_state[f"y_outer_{idx}"] = comp.get('outer', 0.0)
            # Update Parts per Stroke Key
            st.session_state[f"y_n_{idx}"] = comp.get('n_count', 1)
            # Update Slot Types Key
            st.session_state[f"y_num_slots_{idx}"] = comp.get('slot_types', 1)
            
            # Update Slot Keys
            for s_idx, slot in enumerate(comp.get('slots', [])):
                st.session_state[f"y_s_area_{idx}_{s_idx}"] = slot.get('area', 0.0)
                st.session_state[f"y_s_cnt_{idx}_{s_idx}"] = slot.get('count', 1)

        # Clear the buffer so we don't reload on every interaction
        del st.session_state['yield_loaded_data']

    # --- SIDEBAR (History) ---
    with st.sidebar:
        st.header("📜 Yield History")
        history_list = load_history_file(YIELD_HISTORY_FILE)
        if history_list:
            for item in history_list:
                with st.expander(f"{item['timestamp']} - {item['name']}"):
                    if st.button("📂 Load", key=f"y_load_{item['id']}"):
                        st.session_state['yield_loaded_data'] = item
                        st.rerun()
                    if st.button("🗑️ Delete", key=f"y_del_hist_{item['id']}"):
                        delete_yield_history_entry(item['id'])
                        st.rerun()

    # --- 1. Global Strip Inputs ---
    st.subheader("1. Strip Parameters")
    
    # Save Name Input
    if 'y_calc_name' not in st.session_state: st.session_state['y_calc_name'] = "New Yield Calc"
    calc_name = st.text_input("Calculation Name (for History)", value=st.session_state['y_calc_name'], key="y_calc_name")
    
    # --- INIT DEFAULTS ---
    if 'y_pitch' not in st.session_state: st.session_state['y_pitch'] = YIELD_DEFAULTS['pitch']
    if 'y_width' not in st.session_state: st.session_state['y_width'] = YIELD_DEFAULTS['sheet_width']
    if 'y_thick' not in st.session_state: st.session_state['y_thick'] = YIELD_DEFAULTS['sheet_thickness']
    if 'y_density' not in st.session_state: st.session_state['y_density'] = YIELD_DEFAULTS['density']
    if 'y_deduction' not in st.session_state: st.session_state['y_deduction'] = YIELD_DEFAULTS['yield_deduction']

    c1, c2, c3 = st.columns(3)
    pitch = c1.number_input(lbl("Pitch (mm)", 'y_pitch', 'pitch', YIELD_DEFAULTS), value=st.session_state['y_pitch'], key='y_pitch', step=0.1)
    width = c2.number_input(lbl("Sheet Width (mm)", 'y_width', 'sheet_width', YIELD_DEFAULTS), value=st.session_state['y_width'], key='y_width', step=0.1)
    thick = c3.number_input(lbl("Thickness (mm)", 'y_thick', 'sheet_thickness', YIELD_DEFAULTS), value=st.session_state['y_thick'], key='y_thick', step=0.01)
    
    c4, c5 = st.columns(2)
    density = c4.number_input(lbl("Density (g/mm³)", 'y_density', 'density', YIELD_DEFAULTS), value=st.session_state['y_density'], key='y_density', format="%.5f", step=0.00001)
    deduction = c5.number_input(lbl("Yield Deduction (%)", 'y_deduction', 'yield_deduction', YIELD_DEFAULTS), value=st.session_state['y_deduction'], key='y_deduction', step=0.1)
    
    st.divider()

    # --- 2. Component Definition Logic ---
    st.subheader("2. Component Definition")
    
    if 'yield_comps' not in st.session_state:
        st.session_state.yield_comps = [{'id': 0, 'outer': 0.0, 'n_count': 1, 'slot_types': 1, 'slots': [{'area':0.0, 'count':1}]}]

    def add_yield_comp():
        new_id = len(st.session_state.yield_comps)
        st.session_state.yield_comps.append({'id': new_id, 'outer': 0.0, 'n_count': 1, 'slot_types': 1, 'slots': [{'area':0.0, 'count':1}]})

    def remove_yield_comp(idx):
        st.session_state.yield_comps.pop(idx)

    total_finish_area = 0.0

    for idx, comp in enumerate(st.session_state.yield_comps):
        if 'n_count' not in comp: comp['n_count'] = 1

        with st.expander(f"Component {idx + 1}", expanded=True):
            r1_col1, r1_col2 = st.columns([5, 1])
            comp['n_count'] = r1_col1.number_input(
                f"Parts per Stroke", 
                value=comp['n_count'], 
                min_value=1, 
                step=1, 
                key=f"y_n_{idx}",
                help="Number of cavities/parts produced in a single press stroke."
            )
            if r1_col2.button("❌", key=f"y_del_{idx}"):
                remove_yield_comp(idx)
                st.rerun()

            comp['outer'] = st.number_input(
                f"Outer Area (mm²)", 
                value=comp['outer'], 
                step=10.0, 
                key=f"y_outer_{idx}"
            )

            st.markdown(f"**Slots / Cutouts**")
            num_slot_types = st.number_input(f"Slot Types", min_value=0, value=comp['slot_types'], key=f"y_num_slots_{idx}")
            comp['slot_types'] = num_slot_types
            
            current_slots = comp.get('slots', [])
            if len(current_slots) < num_slot_types:
                current_slots.extend([{'area': 0.0, 'count': 1} for _ in range(num_slot_types - len(current_slots))])
            elif len(current_slots) > num_slot_types:
                current_slots = current_slots[:num_slot_types]
            comp['slots'] = current_slots

            total_slots_area = 0.0
            if num_slot_types > 0:
                cols = st.columns([2, 1, 2])
                cols[0].caption("Area per Slot (mm²)")
                cols[1].caption("Count per Part")
                cols[2].caption("Total Subtraction")
                
                for s_idx, slot in enumerate(comp['slots']):
                    s_c1, s_c2, s_c3 = st.columns([2, 1, 2])
                    
                    slot['area'] = s_c1.number_input(
                        "Slot Area", 
                        value=slot['area'], 
                        step=1.0, 
                        key=f"y_s_area_{idx}_{s_idx}", 
                        label_visibility="collapsed"
                    )
                    
                    slot['count'] = s_c2.number_input(
                        "Slot Count", 
                        value=slot['count'], 
                        min_value=1, 
                        step=1, 
                        key=f"y_s_cnt_{idx}_{s_idx}", 
                        label_visibility="collapsed"
                    )
                    
                    sub_total = slot['area'] * slot['count']
                    s_c3.write(f"- {sub_total:.2f}")
                    total_slots_area += sub_total

            single_comp_net_area = comp['outer'] - total_slots_area
            total_comp_area = single_comp_net_area * comp['n_count']
            single_comp_weight = single_comp_net_area * thick * density
            total_finish_area += total_comp_area
            
            st.info(f"**Net Area:** {single_comp_net_area:.2f} mm²  |  **Weight:** {single_comp_weight:.3f} g  |  **Total Area (x{comp['n_count']}):** {total_comp_area:.2f} mm²")

    st.button("➕ Add Another Component", on_click=add_yield_comp)

    # --- 3. Final Calculations ---
    sheet_area = pitch * width
    if sheet_area > 0:
        gross_yield = (total_finish_area / sheet_area) * 100
    else:
        gross_yield = 0
    net_yield = gross_yield - deduction
    gross_weight = sheet_area * thick * density
    net_weight = total_finish_area * thick * density

    # --- 4. Results ---
    st.divider()
    st.header("Results")
    a1, a2 = st.columns(2)
    a1.metric("Total Finish Area", f"{total_finish_area:.2f} mm²", help="Sum of (Net Area × Parts/Stroke)")
    a2.metric("Strip Area (1 Pitch)", f"{sheet_area:.2f} mm²", help="Pitch × Width")

    w1, w2 = st.columns(2)
    w1.metric("Gross Weight (Strip)", f"{gross_weight:.3f} g")
    w2.metric("Net Weight (Finished)", f"{net_weight:.3f} g")

    y1, y2 = st.columns(2)
    y1.metric("Gross Yield", f"{gross_yield:.2f} %")
    y2.metric("Net Yield ( - Deduction)", f"{net_yield:.2f} %", delta=f"-{deduction}")
    
    st.divider()
    if st.button("💾 Save Calculation to History", key="y_save_btn"):
        global_inputs = {'y_pitch': pitch, 'y_width': width, 'y_thick': thick, 'y_density': density, 'y_deduction': deduction}
        saved = save_yield_state(calc_name, global_inputs, st.session_state.yield_comps)
        st.success(f"Saved: {saved['name']}")
        st.rerun()

# ==========================================
# 6. Page: Login & Home
# ==========================================
def page_login():
    st.title("Login")
    password = st.text_input("Enter Password", type="password")
    if st.button("Login"):
        if password == PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Incorrect Password")

def page_home():
    col1, col2 = st.columns([1, 2])
    with col1:
        if os.path.exists(LOGO_FILE):
            st.image(LOGO_FILE, width=200)
    with col2:
        st.title("Sai Precision Tool Industries")
        st.subheader("Internal Costing & Engineering Portal")
        st.markdown("""
        Welcome to the SPTI Digital Tool Suite.
        
        **Available Modules:**
        * **Component Cost Calculator**: Estimate lamination and stack costs.
        * **Yield Calculator**: Calculate material efficiency and weights.
        """)

# ==========================================
# 7. Main Router
# ==========================================
def main():
    st.set_page_config(page_title="SPTI Portal", layout="wide", page_icon="🏭")
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    with st.sidebar:
        if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, width=120)
        st.title("Navigation")
        page = st.radio("Go to", ["Home", "Yield Calculator", "Cost Calculator"])
        st.markdown("---")
        if st.session_state.logged_in:
            st.write("👤 **Admin Mode**")
            if st.button("Log Out"):
                st.session_state.logged_in = False
                st.rerun()
        else:
            st.write("👤 Guest Mode")

    # --- Routing ---
    if page == "Home":
        page_home()

    elif page == "Yield Calculator":
        page_yield_calculator()

    elif page == "Cost Calculator":
        if st.session_state.logged_in:
            page_cost_calculator()
        else:
            # THIS IS CRITICAL: ensure NOTHING else runs if not logged in
            st.warning("🔒 This module requires Administrator Access.")
            page_login()

if __name__ == "__main__":
    main()