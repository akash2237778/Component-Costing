package handlers

import (
	"math/rand"
	"net/http"
	"time"

	"precision-quote/database"
	"precision-quote/types"

	"github.com/gin-contrib/sessions"
	"github.com/gin-gonic/gin"
)

func ShowDashboard(c *gin.Context) {
	session := sessions.Default(c)
	username := session.Get("username")
	role := session.Get("role")

	var s types.Settings
	database.DB.QueryRow("SELECT cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch, ht_rate FROM settings WHERE id=1").Scan(&s.CNCRate, &s.WireCutRate, &s.SquaringRate, &s.HTRate)

	// Fetch standard templates
	rows, _ := database.DB.Query("SELECT id, name, shape FROM component_templates ORDER BY display_order")

	// Convert to ComponentUI (the smart struct)
	var components []types.ComponentUI
	for rows.Next() {
		var c types.ComponentUI
		rows.Scan(&c.ID, &c.Name, &c.Shape)
		// Set defaults for new form
		c.Quantity = 1
		c.IncludeSquaring = true
		c.IncludeHT = false // Default unchecked
		components = append(components, c)
	}

	matRows, _ := database.DB.Query("SELECT id, name FROM materials")
	var materials []types.Material
	for matRows.Next() {
		var m types.Material
		matRows.Scan(&m.ID, &m.Name)
		materials = append(materials, m)
	}

	c.HTML(http.StatusOK, "index.html", gin.H{
		"Components": components,
		"Materials":  materials,
		"Rates":      s,
		"User":       username,
		"IsAdmin":    role == "ADMIN",
		"IsLoadMode": false, // Tells JS to run auto-restore
	})
}

func AddRow(c *gin.Context) {
	rand.Seed(time.Now().UnixNano())
	newID := rand.Intn(90000) + 1000

	matRows, _ := database.DB.Query("SELECT id, name FROM materials")
	var materials []types.Material
	for matRows.Next() {
		var m types.Material
		matRows.Scan(&m.ID, &m.Name)
		materials = append(materials, m)
	}

	// Create a single ComponentUI instance for the template
	comp := types.ComponentUI{
		ID:              newID,
		Name:            "New Component",
		Shape:           "Cuboid",
		Quantity:        1,
		IncludeSquaring: true,
	}

	c.HTML(http.StatusOK, "row.html", gin.H{
		"Component": comp, // Pass as "Component" object to match row.html expectations
		"Materials": materials,
	})
}

func RemoveRow(c *gin.Context) {
	c.String(http.StatusOK, "")
}
