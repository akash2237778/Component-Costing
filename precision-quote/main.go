package main

import (
	"fmt"
	"math"
	"math/rand"
	"net/http"
	"time"

	"precision-quote/database"

	"github.com/gin-gonic/gin"
)

type CalcRequest struct {
	ComponentID int    `form:"component_id"`
	Shape       string `form:"shape"`
	MaterialID  int    `form:"material_id"`

	// INPUTS IN MM
	Length float64 `form:"length"`
	Width  float64 `form:"width"`
	Height float64 `form:"height"`

	ManualPrice float64 `form:"manual_price"`

	IncludeSquaring bool `form:"include_squaring"`
	IncludeHT       bool `form:"include_ht"`

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

		rows, _ := database.DB.Query("SELECT id, name, shape FROM component_templates ORDER BY display_order")
		var components []map[string]interface{}
		for rows.Next() {
			var id int
			var name, shape string
			rows.Scan(&id, &name, &shape)
			components = append(components, map[string]interface{}{"ID": id, "Name": name, "Shape": shape})
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

	// --- 2. ROW MANAGEMENT ---
	r.GET("/component/add", func(c *gin.Context) {
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

		c.HTML(http.StatusOK, "row.html", gin.H{
			"ID":        newID,
			"Name":      "New Component",
			"Shape":     "Cuboid",
			"Materials": materials,
		})
	})

	r.DELETE("/component/remove", func(c *gin.Context) {
		c.String(http.StatusOK, "")
	})

	// --- 3. SETTINGS HANDLERS ---
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
		c.HTML(http.StatusOK, "settings.html", gin.H{"Settings": s, "Materials": materials})
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

		// Defaults (using Steel KG/MM3 now)
		densityFactor := 0.00000785
		ratePerKg := 0.0
		if req.MaterialID > 0 {
			database.DB.QueryRow("SELECT density_factor, rate_per_kg FROM materials WHERE id=?", req.MaterialID).Scan(&densityFactor, &ratePerKg)
		}

		var volumeMM, surfaceAreaMM, surfaceAreaInch, weightKg, rawMatCost, squaringCost, htCost float64

		if req.Shape == "Fixed" {
			rawMatCost = req.ManualPrice
			weightKg = 0
			squaringCost = 0
			htCost = 0
		} else if req.Shape == "Cylindrical" {
			// CYLINDER (Dimensions in MM)
			radius := req.Width / 2.0
			volumeMM = math.Pi * (radius * radius) * req.Length
			surfaceAreaMM = (2 * math.Pi * radius * req.Length) + (2 * math.Pi * radius * radius)

			weightKg = volumeMM * densityFactor // Direct MM calculation

			// Squaring Rate is per Sq Inch, so we convert Area
			surfaceAreaInch = surfaceAreaMM / 645.16

			if req.IncludeSquaring {
				squaringCost = surfaceAreaInch * s.SquaringRate
			}
			if req.IncludeHT {
				htCost = weightKg * s.HTRate
			}
		} else {
			// CUBOID (Dimensions in MM)
			volumeMM = req.Length * req.Width * req.Height
			surfaceAreaMM = 2 * ((req.Length * req.Width) + (req.Length * req.Height) + (req.Width * req.Height))

			weightKg = volumeMM * densityFactor // Direct MM calculation

			// Squaring Rate is per Sq Inch, so we convert Area
			surfaceAreaInch = surfaceAreaMM / 645.16

			if req.IncludeSquaring {
				squaringCost = surfaceAreaInch * s.SquaringRate
			}
			if req.IncludeHT {
				htCost = weightKg * s.HTRate
			}
		}

		rawMatCost = weightKg * ratePerKg

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
			req.ComponentID, surfaceAreaInch,
			req.ComponentID, squaringCost,
			req.ComponentID, htCost,
			req.ComponentID, cncCost,
			req.ComponentID, wireCutCost)

		c.Writer.Header().Set("Content-Type", "text/html")
		c.String(http.StatusOK, response)
	})

	r.Run(":8080")
}
