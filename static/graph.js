var svg = d3.select("svg"),
    margin = {top: 20, right: 80, bottom: 30, left: 50},
    width = window.innerWidth - 8 - 40 - margin.left - margin.right, // svg.attr("width") - margin.left - margin.right,
    height = svg.attr("height") - margin.top - margin.bottom,
    g = svg.append("g").attr("transform", "translate(" + margin.left + "," + margin.top + ")");

var parseTime = d3.timeParse("%Y-%m-%d");

var x = d3.scaleTime().range([0, width]),
    y = d3.scaleLinear().range([height, 0]),// d3.scalePow().exponent(0.5).range([height, 0]),
    z = d3.scaleOrdinal(d3.schemeCategory10);

var line = d3.line()
    .curve(d3.curveBasis)
    .x(function(d) { return x(d.date); })
    .y(function(d) { return y(d.tests); });

var pos = 0;
function positionLegend() {
  var labelWidth = 100;
  pos += labelWidth;
  return pos;
}

d3.csv("data.csv", type, function(error, data) {
  if (error) throw error;

  var groups = data.columns.slice(1).map(function(id) {
    return {
      id: id,
      values: data.map(function(d) {
        return {date: d.date, tests: d[id]};
      })
    };
  });

  x.domain(d3.extent(data, function(d) { return d.date; }));

  y.domain([
    d3.min(groups, function(c) { return d3.min(c.values, function(d) { return d.tests; }); }),
    d3.max(groups, function(c) { return d3.max(c.values, function(d) { return d.tests; }); })
  ]);

  z.domain(groups.map(function(c) { return c.id; }));

  g.append("g")
      .attr("class", "axis axis--x")
      .attr("transform", "translate(0," + height + ")")
      .call(d3.axisBottom(x));

  g.append("g")
      .attr("class", "axis axis--y")
      .call(d3.axisLeft(y).tickArguments([6]))
    .append("text")
      .attr("transform", "rotate(-90)")
      .attr("y", 6)
      .attr("dy", "0.71em")
      .attr("fill", "#000")
      .text("Tests");

  var group = g.selectAll(".group")
    .data(groups)
    .enter().append("g")
      .attr("class", "group");

  group.append("path")
      .attr("class", "line")
      .attr("d", function(d) { return line(d.values); })
      .style("stroke", function(d) { return z(d.id); });

  group.append("text")
      .datum(function(d) { return {id: d.id, value: d.values[d.values.length - 1]}; })
      .attr("transform", function(d) { return "translate(" + positionLegend() + ", " + (y(d.value.tests) - 5) + ")"; })
      .style("font", "10px sans-serif")
      .style("fill", function(d) { return z(d.id); })
      .text(function(d) { return d.id; });
});

function type(d, _, columns) {
  d.date = parseTime(d.date);
  for (var i = 1, n = columns.length, c; i < n; ++i) d[c = columns[i]] = +d[c];
  return d;
}
