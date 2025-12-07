package handlers

import (
	"net/http"

	"precision-quote/database"
	"precision-quote/types"

	"github.com/gin-gonic/gin"
)

func ShowSettings(c *gin.Context) {
	var s types.Settings
	database.DB.QueryRow("SELECT cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch, ht_rate FROM settings WHERE id=1").Scan(&s.CNCRate, &s.WireCutRate, &s.SquaringRate, &s.HTRate)

	matRows, _ := database.DB.Query("SELECT id, name, density_factor, rate_per_kg FROM materials")
	var materials []types.Material
	for matRows.Next() {
		var m types.Material
		matRows.Scan(&m.ID, &m.Name, &m.Density, &m.Rate)
		materials = append(materials, m)
	}

	c.HTML(http.StatusOK, "settings.html", gin.H{
		"Settings":  s,
		"Materials": materials,
	})
}

func UpdateGlobal(c *gin.Context) {
	var s types.Settings
	if err := c.ShouldBind(&s); err != nil {
		return
	}
	database.DB.Exec("UPDATE settings SET cnc_rate_hourly=?, wirecut_rate_mm=?, squaring_rate_sqinch=?, ht_rate=? WHERE id=1", s.CNCRate, s.WireCutRate, s.SquaringRate, s.HTRate)
	c.Status(http.StatusOK)
}

func UpdateMaterial(c *gin.Context) {
	id := c.PostForm("id")
	name := c.PostForm("name")
	density := c.PostForm("density")
	rate := c.PostForm("rate")
	database.DB.Exec("UPDATE materials SET name=?, density_factor=?, rate_per_kg=? WHERE id=?", name, density, rate, id)
	c.Status(http.StatusOK)
}

func AddMaterial(c *gin.Context) {
	name := c.PostForm("name")
	density := c.PostForm("density")
	rate := c.PostForm("rate")
	database.DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES (?, ?, ?)", name, density, rate)
	c.Redirect(http.StatusSeeOther, "/settings")
}
