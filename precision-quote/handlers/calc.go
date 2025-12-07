package handlers

import (
	"fmt"
	"math"
	"net/http"

	"precision-quote/database"
	"precision-quote/types"

	"github.com/gin-gonic/gin"
)

func Calculate(c *gin.Context) {
	var req types.CalcRequest
	if err := c.ShouldBind(&req); err != nil {
		fmt.Println("Bind Error:", err)
	}

	var s types.Settings
	database.DB.QueryRow("SELECT cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch, ht_rate FROM settings WHERE id=1").Scan(&s.CNCRate, &s.WireCutRate, &s.SquaringRate, &s.HTRate)

	densityFactor := 0.00000785 // Default Steel (Kg/mm3)
	ratePerKg := 0.0
	if req.MaterialID > 0 {
		database.DB.QueryRow("SELECT density_factor, rate_per_kg FROM materials WHERE id=?", req.MaterialID).Scan(&densityFactor, &ratePerKg)
	}

	var volumeMM, surfaceAreaMM, surfaceAreaInch, weightKg, rawMatCost, squaringCost, htCost float64

	if req.Shape == "Fixed" {
		rawMatCost = req.ManualPrice
	} else if req.Shape == "Cylindrical" {
		// Cylinder: Width is Diameter
		radius := req.Width / 2.0
		volumeMM = math.Pi * (radius * radius) * req.Length
		surfaceAreaMM = (2 * math.Pi * radius * req.Length) + (2 * math.Pi * radius * radius)

		weightKg = volumeMM * densityFactor

		surfaceAreaInch = surfaceAreaMM / 645.16
		if req.IncludeSquaring {
			squaringCost = surfaceAreaInch * s.SquaringRate
		}
		if req.IncludeHT {
			htCost = weightKg * s.HTRate
		}
	} else {
		// Cuboid
		volumeMM = req.Length * req.Width * req.Height
		surfaceAreaMM = 2 * ((req.Length * req.Width) + (req.Length * req.Height) + (req.Width * req.Height))

		weightKg = volumeMM * densityFactor

		surfaceAreaInch = surfaceAreaMM / 645.16
		if req.IncludeSquaring {
			squaringCost = surfaceAreaInch * s.SquaringRate
		}
		if req.IncludeHT {
			htCost = weightKg * s.HTRate
		}
	}

	if req.Shape != "Fixed" {
		rawMatCost = weightKg * ratePerKg
	}

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
}
