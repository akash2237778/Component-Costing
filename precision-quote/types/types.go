package types

// CalcRequest holds the form data sent by HTMX
type CalcRequest struct {
	ComponentID     int     `form:"component_id"`
	Shape           string  `form:"shape"`
	MaterialID      int     `form:"material_id"`
	Length          float64 `form:"length"`
	Width           float64 `form:"width"`
	Height          float64 `form:"height"`
	ManualPrice     float64 `form:"manual_price"`
	IncludeSquaring bool    `form:"include_squaring"`
	IncludeHT       bool    `form:"include_ht"`
	Quantity        int     `form:"quantity"`
	CNCHours        float64 `form:"cnc_hours"`
	WireCutLen      float64 `form:"wirecut_len"`
	DrillingCost    float64 `form:"drilling_cost"`
}

// Settings holds global rates
type Settings struct {
	CNCRate      float64 `form:"cnc_rate"`
	WireCutRate  float64 `form:"wirecut_rate"`
	SquaringRate float64 `form:"squaring_rate"`
	HTRate       float64 `form:"ht_rate"`
}

// Material represents a metal type
type Material struct {
	ID      int
	Name    string  `form:"name"`
	Density float64 `form:"density"`
	Rate    float64 `form:"rate"`
}
