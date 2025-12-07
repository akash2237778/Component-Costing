package types

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

type QuoteSubmission struct {
	CustomerName string      `json:"customer_name"`
	ToolName     string      `json:"tool_name"`
	GrandTotal   float64     `json:"grand_total"`
	Items        []QuoteItem `json:"items"`
}

type QuoteItem struct {
	ComponentName   string  `json:"component_name"`
	Shape           string  `json:"shape"`
	MaterialID      int     `json:"material_id"`
	Length          float64 `json:"length"`
	Width           float64 `json:"width"`
	Height          float64 `json:"height"`
	ManualPrice     float64 `json:"manual_price"`
	Quantity        int     `json:"quantity"`
	RowCost         float64 `json:"row_cost"`
	IncludeSquaring bool    `json:"include_squaring"`
	IncludeHT       bool    `json:"include_ht"`
}

// ComponentUI is used to render the rows in index.html
type ComponentUI struct {
	ID              int
	Name            string
	Shape           string
	MaterialID      int
	Length          float64
	Width           float64
	Height          float64
	ManualPrice     float64
	Quantity        int
	IncludeSquaring bool
	IncludeHT       bool
	RowCost         float64

	// NEW: Display fields for history loading
	Weight      float64
	Area        float64
	PreMachCost float64
	HTCost      float64
	CNCCost     float64
	WireCost    float64
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
