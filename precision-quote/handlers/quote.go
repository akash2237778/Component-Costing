package handlers

import (
	"database/sql"
	"math"
	"net/http"
	"time"

	"precision-quote/database"
	"precision-quote/types"

	"github.com/gin-contrib/sessions"
	"github.com/gin-gonic/gin"
)

// API: Save Quote with Versioning & Duplicate Check
func SaveQuote(c *gin.Context) {
	var req types.QuoteSubmission
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	session := sessions.Default(c)
	user := session.Get("username").(string)

	var quoteNumber int
	var version int

	if req.QuoteNumber == 0 {
		// New Quote
		err := database.DB.QueryRow("SELECT COALESCE(MAX(quote_number), 1000) + 1 FROM quotes").Scan(&quoteNumber)
		if err != nil {
			quoteNumber = 1001
		}
		version = 1
	} else {
		// Update (New Version)
		quoteNumber = req.QuoteNumber

		// 1. DUPLICATE CHECK
		// Fetch the latest version's details to compare
		var lastTotal float64
		var lastTool string
		err := database.DB.QueryRow("SELECT total_cost, tool_name FROM quotes WHERE quote_number = ? ORDER BY version DESC LIMIT 1", quoteNumber).Scan(&lastTotal, &lastTool)

		if err == nil {
			// Compare Float (using small epsilon) and String
			if math.Abs(lastTotal-req.GrandTotal) < 0.01 && lastTool == req.ToolName {
				c.JSON(http.StatusConflict, gin.H{"error": "No changes detected (Exact same cost & name as previous version)"})
				return
			}
		}

		// 2. Get Next Version
		err = database.DB.QueryRow("SELECT COALESCE(MAX(version), 0) + 1 FROM quotes WHERE quote_number = ?", quoteNumber).Scan(&version)
		if err != nil {
			version = 1
		}
	}

	// Insert Header
	res, err := database.DB.Exec("INSERT INTO quotes (quote_number, version, customer_name, tool_name, total_cost, created_by) VALUES (?, ?, ?, ?, ?, ?)",
		quoteNumber, version, req.CustomerName, req.ToolName, req.GrandTotal, user)

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Database Error"})
		return
	}

	internalID, _ := res.LastInsertId()

	// Insert Items
	stmt, _ := database.DB.Prepare(`INSERT INTO quote_items 
		(quote_id, component_name, shape, material_id, length, width, height, manual_price, quantity, final_cost, include_squaring, include_ht) 
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)

	for _, item := range req.Items {
		stmt.Exec(internalID, item.ComponentName, item.Shape, item.MaterialID, item.Length, item.Width, item.Height, item.ManualPrice, item.Quantity, item.RowCost, item.IncludeSquaring, item.IncludeHT)
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "quote_number": quoteNumber, "version": version})
}

// Page: History List (Grouped)
func ShowHistory(c *gin.Context) {
	session := sessions.Default(c)
	user := session.Get("username")
	isAdmin := session.Get("role") == "ADMIN"

	rows, _ := database.DB.Query("SELECT id, quote_number, version, customer_name, tool_name, total_cost, created_by, created_at FROM quotes ORDER BY quote_number DESC, version DESC")

	type QuoteRow struct {
		ID           int
		QuoteNumber  int
		Version      int
		CustomerName string
		ToolName     string
		TotalCost    float64
		CreatedBy    string
		Date         time.Time
	}

	// Grouping Structure
	type QuoteGroup struct {
		Latest  QuoteRow
		History []QuoteRow
	}

	var groups []QuoteGroup
	var currentGroup *QuoteGroup

	for rows.Next() {
		var q QuoteRow
		var custName sql.NullString
		rows.Scan(&q.ID, &q.QuoteNumber, &q.Version, &custName, &q.ToolName, &q.TotalCost, &q.CreatedBy, &q.Date)

		if isAdmin {
			q.CustomerName = custName.String
		} else {
			q.CustomerName = "🔒 Restricted"
		}

		// Logic to Group by QuoteNumber
		// Since SQL orders by QuoteNumber DESC, we know same numbers come sequentially
		if currentGroup == nil || currentGroup.Latest.QuoteNumber != q.QuoteNumber {
			// Start new group
			if currentGroup != nil {
				groups = append(groups, *currentGroup)
			}
			currentGroup = &QuoteGroup{Latest: q, History: []QuoteRow{}}
		} else {
			// Add to existing group history
			currentGroup.History = append(currentGroup.History, q)
		}
	}
	// Append the final group
	if currentGroup != nil {
		groups = append(groups, *currentGroup)
	}

	c.HTML(http.StatusOK, "history.html", gin.H{
		"Groups":  groups,
		"User":    user,
		"IsAdmin": isAdmin,
	})
}

// Page: Load Quote (Unchanged logic, just copy-paste from previous phase if needed or keep existing)
func LoadQuote(c *gin.Context) {
	quoteID := c.Param("id")
	session := sessions.Default(c)
	username := session.Get("username")
	role := session.Get("role")

	var quoteNum, ver int
	var customer, tool string

	err := database.DB.QueryRow("SELECT quote_number, version, customer_name, tool_name FROM quotes WHERE id=?", quoteID).Scan(&quoteNum, &ver, &customer, &tool)
	if err != nil {
		c.Redirect(http.StatusFound, "/history")
		return
	}

	if role != "ADMIN" {
		customer = ""
	}

	var s types.Settings
	database.DB.QueryRow("SELECT cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch, ht_rate FROM settings WHERE id=1").Scan(&s.CNCRate, &s.WireCutRate, &s.SquaringRate, &s.HTRate)

	rows, _ := database.DB.Query(`SELECT id, component_name, shape, material_id, length, width, height, manual_price, quantity, final_cost, include_squaring, include_ht 
		FROM quote_items WHERE quote_id=?`, quoteID)

	var components []types.ComponentUI
	for rows.Next() {
		var item types.ComponentUI
		rows.Scan(&item.ID, &item.Name, &item.Shape, &item.MaterialID, &item.Length, &item.Width, &item.Height, &item.ManualPrice, &item.Quantity, &item.RowCost, &item.IncludeSquaring, &item.IncludeHT)

		if item.Shape != "Fixed" {
			densityFactor := 0.00000785
			if item.MaterialID > 0 {
				database.DB.QueryRow("SELECT density_factor FROM materials WHERE id=?", item.MaterialID).Scan(&densityFactor)
			}

			var volMM, surfMM, surfInch float64

			if item.Shape == "Cylindrical" {
				radius := item.Width / 2.0
				volMM = math.Pi * (radius * radius) * item.Length
				surfMM = (2 * math.Pi * radius * item.Length) + (2 * math.Pi * radius * radius)
			} else {
				volMM = item.Length * item.Width * item.Height
				surfMM = 2 * ((item.Length * item.Width) + (item.Length * item.Height) + (item.Width * item.Height))
			}

			item.Weight = volMM * densityFactor
			surfInch = surfMM / 645.16
			item.Area = surfInch

			if item.IncludeSquaring {
				item.PreMachCost = surfInch * s.SquaringRate
			}
			if item.IncludeHT {
				item.HTCost = item.Weight * s.HTRate
			}
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
		"QuoteID":      quoteID,
		"QuoteNumber":  quoteNum,
		"Version":      ver,
		"CustomerName": customer,
		"ToolName":     tool,
	})
}
