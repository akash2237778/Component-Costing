package handlers

import (
	"math"
	"net/http"
	"time"

	"github.com/gin-contrib/sessions"
	"github.com/gin-gonic/gin"
	"precision-quote/database"
	"precision-quote/types"
)

// API: Save Quote (Unchanged)
func SaveQuote(c *gin.Context) {
	var req types.QuoteSubmission
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	session := sessions.Default(c)
	user := session.Get("username").(string)

	res, err := database.DB.Exec("INSERT INTO quotes (customer_name, tool_name, total_cost, created_by) VALUES (?, ?, ?, ?)",
		req.CustomerName, req.ToolName, req.GrandTotal, user)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Database Error"})
		return
	}
	quoteID, _ := res.LastInsertId()

	stmt, _ := database.DB.Prepare(`INSERT INTO quote_items 
		(quote_id, component_name, shape, material_id, length, width, height, manual_price, quantity, final_cost, include_squaring, include_ht) 
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
	
	for _, item := range req.Items {
		stmt.Exec(quoteID, item.ComponentName, item.Shape, item.MaterialID, item.Length, item.Width, item.Height, item.ManualPrice, item.Quantity, item.RowCost, item.IncludeSquaring, item.IncludeHT)
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "id": quoteID})
}

// Page: History List (Unchanged)
func ShowHistory(c *gin.Context) {
	session := sessions.Default(c)
	user := session.Get("username")
	isAdmin := session.Get("role") == "ADMIN"

	rows, _ := database.DB.Query("SELECT id, customer_name, tool_name, total_cost, created_by, created_at FROM quotes ORDER BY created_at DESC")
	
	type QuoteHistory struct {
		ID           int
		CustomerName string
		ToolName     string
		TotalCost    float64
		CreatedBy    string
		Date         time.Time
	}

	var history []QuoteHistory
	for rows.Next() {
		var q QuoteHistory
		rows.Scan(&q.ID, &q.CustomerName, &q.ToolName, &q.TotalCost, &q.CreatedBy, &q.Date)
		history = append(history, q)
	}

	c.HTML(http.StatusOK, "history.html", gin.H{
		"Quotes":  history,
		"User":    user,
		"IsAdmin": isAdmin,
	})
}

// Page: Load Quote (UPDATED)
func LoadQuote(c *gin.Context) {
	quoteID := c.Param("id")
	session := sessions.Default(c)
	username := session.Get("username")
	role := session.Get("role")

	// 1. Fetch Header
	var customer, tool string
	err := database.DB.QueryRow("SELECT customer_name, tool_name FROM quotes WHERE id=?", quoteID).Scan(&customer, &tool)
	if err != nil {
		c.Redirect(http.StatusFound, "/history")
		return
	}

	// 2. Fetch Rates (To re-calculate display values)
	var s types.Settings
	database.DB.QueryRow("SELECT cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch, ht_rate FROM settings WHERE id=1").Scan(&s.CNCRate, &s.WireCutRate, &s.SquaringRate, &s.HTRate)

	// 3. Fetch Items
	rows, _ := database.DB.Query(`SELECT id, component_name, shape, material_id, length, width, height, manual_price, quantity, final_cost, include_squaring, include_ht 
		FROM quote_items WHERE quote_id=?`, quoteID)

	var components []types.ComponentUI
	for rows.Next() {
		var item types.ComponentUI
		rows.Scan(&item.ID, &item.Name, &item.Shape, &item.MaterialID, &item.Length, &item.Width, &item.Height, &item.ManualPrice, &item.Quantity, &item.RowCost, &item.IncludeSquaring, &item.IncludeHT)
		
		// --- RE-CALCULATE DISPLAY VALUES ---
		if item.Shape != "Fixed" {
			// Get Density
			densityFactor := 0.00000785
			if item.MaterialID > 0 {
				database.DB.QueryRow("SELECT density_factor FROM materials WHERE id=?", item.MaterialID).Scan(&densityFactor)
			}

			// Dimensions (MM to Inch for Squaring, MM for Weight)
			var volMM, surfMM float64
			
			if item.Shape == "Cylindrical" {
				radius := item.Width / 2.0
				volMM = math.Pi * (radius * radius) * item.Length
				surfMM = (2 * math.Pi * radius * item.Length) + (2 * math.Pi * radius * radius)
			} else {
				volMM = item.Length * item.Width * item.Height
				surfMM = 2 * ((item.Length * item.Width) + (item.Length * item.Height) + (item.Width * item.Height))
			}

			item.Weight = volMM * densityFactor
			item.Area = surfMM / 645.16 // Convert mm2 to Inch2

			if item.IncludeSquaring {
				item.PreMachCost = item.Area * s.SquaringRate
			}
			if item.IncludeHT {
				item.HTCost = item.Weight * s.HTRate
			}
			
			// We can't easily recover exact CNC Hours/Wire Length from "RowCost" alone without storing them.
			// Ideally, you should add 'cnc_hours' and 'wire_len' columns to 'quote_items' table.
			// For now, these will remain 0 unless you update the DB schema.
			// However, since we have the inputs filled in index.html, HTMX will re-calc them on first edit.
		}

		components = append(components, item)
	}

	matRows, _ := database.DB.Query("SELECT id, name FROM materials")
	var materials []types.Material
	for matRows.Next() {
		var m types.Material
		matRows.Scan(&m.ID, &m.Name)
		materials = append(materials, m)
	}

	c.HTML(http.StatusOK, "index.html", gin.H{
		"Components":   components,
		"Materials":    materials,
		"Rates":        s,
		"User":         username,
		"IsAdmin":      role == "ADMIN",
		"IsLoadMode":   true,
		"CustomerName": customer,
		"ToolName":     tool,
	})
}