package main

import (
	"fmt"
	"math/rand"
	"net/http"
	"time"

	"precision-quote/database"

	"github.com/gin-gonic/gin"
)

// --- STRUCTS ---
type CalcRequest struct {
	ComponentID  int     `form:"component_id"`
	MaterialID   int     `form:"material_id"`
	Length       float64 `form:"length"`
	Width        float64 `form:"width"`
	Height       float64 `form:"height"`
	Quantity     int     `form:"quantity"`
	CNCHours     float64 `form:"cnc_hours"`
	WireCutLen   float64 `form:"wirecut_len"`
	DrillingCost float64 `form:"drilling_cost"`
}

type Settings struct {
	CNCRate      float64 `form:"cnc_rate"`
	WireCutRate  float64 `form:"wirecut_rate"`
	SquaringRate float64 `form:"squaring_rate"`
	HTRate       float64 `form:"ht_rate"`
}

type Material struct {
	ID      int
	Name    string  `form:"name"`
	Density float64 `form:"density"`
	Rate    float64 `form:"rate"`
}

func main() {
	database.InitDB()
	r := gin.Default()
	r.LoadHTMLGlob("templates/*")

	// --- 1. DASHBOARD ---
	r.GET("/", func(c *gin.Context) {
		var s Settings
		database.DB.QueryRow("SELECT cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch, ht_rate FROM settings WHERE id=1").Scan(&s.CNCRate, &s.WireCutRate, &s.SquaringRate, &s.HTRate)

		rows, _ := database.DB.Query("SELECT id, name FROM component_templates ORDER BY display_order")
		var components []map[string]interface{}
		for rows.Next() {
			var id int
			var name string
			rows.Scan(&id, &name)
			components = append(components, map[string]interface{}{"ID": id, "Name": name})
		}

		matRows, _ := database.DB.Query("SELECT id, name FROM materials")
		var materials []map[string]interface{}
		for matRows.Next() {
			var id int
			var name string
			matRows.Scan(&id, &name)
			materials = append(materials, map[string]interface{}{"ID": id, "Name": name})
		}

		c.HTML(http.StatusOK, "index.html", gin.H{
			"Components": components,
			"Materials":  materials,
			"Rates":      s,
		})
	})

	// --- 2. ROW MANAGEMENT (Add/Remove) ---

	// Add New Row (Returns HTML Fragment)
	r.GET("/component/add", func(c *gin.Context) {
		// Generate a random ID for the new row (1000+) to avoid conflict with DB IDs
		rand.Seed(time.Now().UnixNano())
		newID := rand.Intn(90000) + 1000

		matRows, _ := database.DB.Query("SELECT id, name FROM materials")
		var materials []map[string]interface{}
		for matRows.Next() {
			var id int
			var name string
			matRows.Scan(&id, &name)
			materials = append(materials, map[string]interface{}{"ID": id, "Name": name})
		}

		// Render a single row using the index.html logic (we use a template block/fragment trick or just raw HTML)
		// For simplicity in Gin without partials, we construct the map and render a dedicated fragment template.
		// NOTE: Since we are using standard LoadHTMLGlob, we need a separate file for the row or inline it.
		// Let's assume we use a "row_fragment.html" or we just serve the logic here.
		// For simplicity, we will create a map and render "row.html"

		c.HTML(http.StatusOK, "row.html", gin.H{
			"ID":        newID,
			"Name":      "New Component",
			"Materials": materials,
		})
	})

	// Remove Row
	r.DELETE("/component/remove", func(c *gin.Context) {
		// Just return empty string to remove element from DOM
		c.String(http.StatusOK, "")
	})

	// --- 3. SETTINGS & ACTIONS ---
	r.GET("/settings", func(c *gin.Context) {
		var s Settings
		database.DB.QueryRow("SELECT cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch, ht_rate FROM settings WHERE id=1").Scan(&s.CNCRate, &s.WireCutRate, &s.SquaringRate, &s.HTRate)

		matRows, _ := database.DB.Query("SELECT id, name, density_factor, rate_per_kg FROM materials")
		var materials []Material
		for matRows.Next() {
			var m Material
			matRows.Scan(&m.ID, &m.Name, &m.Density, &m.Rate)
			materials = append(materials, m)
		}

		c.HTML(http.StatusOK, "settings.html", gin.H{
			"Settings":  s,
			"Materials": materials,
		})
	})

	r.POST("/settings/global", func(c *gin.Context) {
		var s Settings
		if err := c.ShouldBind(&s); err != nil {
			return
		}
		database.DB.Exec("UPDATE settings SET cnc_rate_hourly=?, wirecut_rate_mm=?, squaring_rate_sqinch=?, ht_rate=? WHERE id=1", s.CNCRate, s.WireCutRate, s.SquaringRate, s.HTRate)
		c.Status(http.StatusOK)
	})

	r.POST("/settings/material/update", func(c *gin.Context) {
		id := c.PostForm("id")
		name := c.PostForm("name")
		density := c.PostForm("density")
		rate := c.PostForm("rate")
		database.DB.Exec("UPDATE materials SET name=?, density_factor=?, rate_per_kg=? WHERE id=?", name, density, rate, id)
		c.Status(http.StatusOK)
	})

	r.POST("/settings/material/add", func(c *gin.Context) {
		name := c.PostForm("name")
		density := c.PostForm("density")
		rate := c.PostForm("rate")
		database.DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES (?, ?, ?)", name, density, rate)
		c.Redirect(http.StatusSeeOther, "/settings")
	})

	// --- 4. CALCULATE ---
	r.POST("/calculate", func(c *gin.Context) {
		var req CalcRequest
		if err := c.ShouldBind(&req); err != nil {
			fmt.Println("Bind Warning")
		}

		var s Settings
		database.DB.QueryRow("SELECT cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch, ht_rate FROM settings WHERE id=1").Scan(&s.CNCRate, &s.WireCutRate, &s.SquaringRate, &s.HTRate)

		densityFactor := 0.1286
		ratePerKg := 0.0
		if req.MaterialID > 0 {
			database.DB.QueryRow("SELECT density_factor, rate_per_kg FROM materials WHERE id=?", req.MaterialID).Scan(&densityFactor, &ratePerKg)
		}

		// Math
		volume := req.Length * req.Width * req.Height
		weightKg := volume * densityFactor
		rawMatCost := weightKg * ratePerKg

		surfaceArea := 2 * ((req.Length * req.Width) + (req.Length * req.Height) + (req.Width * req.Height))
		squaringCost := surfaceArea * s.SquaringRate

		htCost := weightKg * s.HTRate

		cncCost := req.CNCHours * s.CNCRate
		wireCutCost := req.WireCutLen * s.WireCutRate

		qty := float64(req.Quantity)
		if req.Quantity == 0 {
			qty = 1.0
		}

		unitTotal := rawMatCost + squaringCost + htCost + cncCost + wireCutCost + req.DrillingCost
		grandTotal := unitTotal * qty

		response := fmt.Sprintf(`
			₹%.2f
			<div id="weight-div-%d" hx-swap-oob="true" class="text-gray-900 font-bold">%.2f kg</div>
			<div id="area-div-%d" hx-swap-oob="true" class="text-gray-900">%.1f sq"</div>
			<div id="pre-mach-div-%d" hx-swap-oob="true" class="text-orange-800 font-bold">₹%.0f</div>
            <div id="ht-div-%d" hx-swap-oob="true" class="text-red-800 font-bold">₹%.0f</div>
            <div id="cnc-cost-div-%d" hx-swap-oob="true" class="text-xs text-gray-400 mt-1 text-center font-mono">₹%.0f</div>
            <div id="wire-cost-div-%d" hx-swap-oob="true" class="text-xs text-gray-400 mt-1 text-center font-mono">₹%.0f</div>
		`, grandTotal,
			req.ComponentID, weightKg,
			req.ComponentID, surfaceArea,
			req.ComponentID, squaringCost,
			req.ComponentID, htCost,
			req.ComponentID, cncCost,
			req.ComponentID, wireCutCost)

		c.Writer.Header().Set("Content-Type", "text/html")
		c.String(http.StatusOK, response)
	})

	r.Run(":8080")
}
