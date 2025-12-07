package main

import (
	"fmt"
	"net/http"

	"precision-quote/database"

	"github.com/gin-gonic/gin"
)

// --- STRUCTS ---
type CalcRequest struct {
	ComponentID int     `form:"component_id"`
	MaterialID  int     `form:"material_id"`
	Length      float64 `form:"length"`
	Width       float64 `form:"width"`
	Height      float64 `form:"height"`
	Quantity    int     `form:"quantity"`
	CNCHours    float64 `form:"cnc_hours"`
	WireCutLen  float64 `form:"wirecut_len"`
	GrindingEst float64 `form:"grinding_est"`
}

type Settings struct {
	CNCRate      float64 `form:"cnc_rate"`
	WireCutRate  float64 `form:"wirecut_rate"`
	SquaringRate float64 `form:"squaring_rate"`
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
		var settings Settings
		database.DB.QueryRow("SELECT cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch FROM settings WHERE id=1").Scan(&settings.CNCRate, &settings.WireCutRate, &settings.SquaringRate)

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
			"Rates":      settings,
		})
	})

	// --- 2. SETTINGS PAGE ---
	r.GET("/settings", func(c *gin.Context) {
		var settings Settings
		database.DB.QueryRow("SELECT cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch FROM settings WHERE id=1").Scan(&settings.CNCRate, &settings.WireCutRate, &settings.SquaringRate)

		matRows, _ := database.DB.Query("SELECT id, name, density_factor, rate_per_kg FROM materials")
		var materials []Material
		for matRows.Next() {
			var m Material
			matRows.Scan(&m.ID, &m.Name, &m.Density, &m.Rate)
			materials = append(materials, m)
		}

		c.HTML(http.StatusOK, "settings.html", gin.H{
			"Settings":  settings,
			"Materials": materials,
		})
	})

	// --- 3. ACTIONS ---

	// Update Global Rates
	r.POST("/settings/global", func(c *gin.Context) {
		var s Settings
		if err := c.ShouldBind(&s); err != nil {
			return
		}
		database.DB.Exec("UPDATE settings SET cnc_rate_hourly=?, wirecut_rate_mm=?, squaring_rate_sqinch=? WHERE id=1", s.CNCRate, s.WireCutRate, s.SquaringRate)
		c.Status(http.StatusOK)
	})

	// Update Existing Material
	r.POST("/settings/material/update", func(c *gin.Context) {
		id := c.PostForm("id")
		name := c.PostForm("name")
		density := c.PostForm("density")
		rate := c.PostForm("rate")

		_, err := database.DB.Exec("UPDATE materials SET name=?, density_factor=?, rate_per_kg=? WHERE id=?", name, density, rate, id)
		if err != nil {
			fmt.Println("Update Error:", err)
		}
		c.Status(http.StatusOK)
	})

	// Add New Material
	r.POST("/settings/material/add", func(c *gin.Context) {
		name := c.PostForm("name")
		density := c.PostForm("density")
		rate := c.PostForm("rate")

		_, err := database.DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES (?, ?, ?)", name, density, rate)
		if err != nil {
			fmt.Println("Insert Error:", err)
		}

		// Reload the settings page to show the new item
		c.Redirect(http.StatusSeeOther, "/settings")
	})

	// --- 4. CALCULATE ---
	r.POST("/calculate", func(c *gin.Context) {
		var req CalcRequest
		if err := c.ShouldBind(&req); err != nil {
			fmt.Println("Bind Warning:", err)
		}

		var s Settings
		database.DB.QueryRow("SELECT cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch FROM settings WHERE id=1").Scan(&s.CNCRate, &s.WireCutRate, &s.SquaringRate)

		// Defaults
		densityFactor := 0.1286
		ratePerKg := 0.0

		// Lookup Material (NOW INCLUDES DENSITY)
		if req.MaterialID > 0 {
			database.DB.QueryRow("SELECT density_factor, rate_per_kg FROM materials WHERE id=?", req.MaterialID).Scan(&densityFactor, &ratePerKg)
		}

		// Math
		volume := req.Length * req.Width * req.Height
		weightKg := volume * densityFactor
		rawMatCost := weightKg * ratePerKg

		surfaceArea := 2 * ((req.Length * req.Width) + (req.Length * req.Height) + (req.Width * req.Height))
		squaringCost := surfaceArea * s.SquaringRate

		cncCost := req.CNCHours * s.CNCRate
		wireCutCost := req.WireCutLen * s.WireCutRate

		qty := float64(req.Quantity)
		if req.Quantity == 0 {
			qty = 1.0
		}

		unitTotal := rawMatCost + squaringCost + cncCost + wireCutCost + req.GrindingEst
		grandTotal := unitTotal * qty

		response := fmt.Sprintf(`
			₹%.2f
			<div id="weight-div-%d" hx-swap-oob="true" class="text-gray-900 font-bold">%.2f kg</div>
			<div id="area-div-%d" hx-swap-oob="true" class="text-gray-900">%.1f sq"</div>
		`, grandTotal, req.ComponentID, weightKg, req.ComponentID, surfaceArea)

		c.Writer.Header().Set("Content-Type", "text/html")
		c.String(http.StatusOK, response)
	})

	r.Run(":8080")
}
