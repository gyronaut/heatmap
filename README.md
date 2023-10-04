# heatmap

### A project to stay motivated in 2020: http://gyronautilus.com/heatmap.html

In 2020, with all organized race events cancelled, I decided I needed a new goal to keep me motivated. This lead me to the question "How much of Austin can I map out just by running from my house?"

This project is the answer to that question.

The code is broken in two parts, one in Python and one in Javascript:
- **Python**: this takes in a collection of .gpx files and converts them to .png heatmap images using a standard web map tile structure. It follows the basic outline found in the Strava dev blog post [here](https://medium.com/strava-engineering/the-global-heatmap-now-6x-hotter-23fc01d301de).
- **Javascript**: This is the web interface, using the [Leaflet](https://leafletjs.com/) library to display these tiles as a standard interactive map. This was extended to include an overlay of a street map, and the ability to draw routes on the map and export them to .gpx files. This let me plan a route that covered new roads directly on the heatmap, and export that route straight to my watch before a run. 
