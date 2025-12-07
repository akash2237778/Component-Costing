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
		"User":       username,
		"IsAdmin":    role == "ADMIN",
	})
}

func AddRow(c *gin.Context) {
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
}

func RemoveRow(c *gin.Context) {
	c.String(http.StatusOK, "")
}
