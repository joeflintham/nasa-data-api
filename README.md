# nasa-data-api
Simple API to access Nasa's climate data

##Nasa Climate Data

On 9 June 2015 Nasa announced they were releasing for public consumption a large dataset detailing historical and projected climate data: recorded temperature and rainfall patterns from 1950 to 2005, and two sets of projected temperature and rainfall patterns from 2006 - 2100. Details at http://climate.nasa.gov/news/2293/
     
For more information on the dataset supplied by Nasa, see https://cds.nccs.nasa.gov/nex-gddp/

##API queries

See http://nasa.stowaway.net/index.cgi/api for an example response.
    
For reasons that will become clear below, it is currently only possible to query one year and measurement, and a small number of locations, at a time. While the API will accept multiple years, measurements, and a point or a bounding box as parameters, the backend can only process the data for one year at a time.

See /templates/index.html.ep (found at / in the installed site) for details of API parameters.

Requests spanning wider timescales are planned for future iterations. See below for details on the planning for these features. 

##Data format

The data is supplied in the NetCDF format: https://en.wikipedia.org/wiki/NetCDF

For each year from 1950 to 2005 there is a NetCDF file for *tasmin* ("Daily Minimum Near-Surface Air Temperature"), *tasmax* (Daily Maximum Near-Surface Air Temperature), and *pr* (Precipitation). Each file is in the region of 700MB or more, meaning that all of the historical data occupies more than 110GB.

For the years 2006 to 2100 there same measures are supplied (tasmin, tasmax and pr), but in two projections: RCP45 ("medium-low" projection) and RCP85 ("high" projection). (See https://en.wikipedia.org/wiki/Representative_Concentration_Pathways for background info on RCP projections). That means
95 years for which there are two sets of three measures.

In total the raw data is likely to occupy over 500GB (I have not yet acquired the two sets of projections), so be aware of this before proceeding to the data acquisition step!    

##Data structure

Each NetCDF file provides datapoints for each measure across three variable dimensions: *lat* (latitude), *lon* (longitude) and *time* (days since 1950-01-01). The geospatial granularity is 0.25 degrees, meaning there are 1440 * 720 * 365 (or 366) datapoints for each year.

In total that means there are a total of 1036800 points on the earth for which there are 3 separate measures for every day between 1950 and 2100 (and two possible projected measurements for each of the 3 * 1036800 datapoints for each day between 2005 and 2100.

In fact the total number of historical datapoints is 20440 days * 1036800 locations * 3 measurements = 63,576,576,000; meanwhile the total number of projected datapoints is 2 projections * 34675 days * 1036800 locations * 3 measurements = 215,706,240,000.

That gives a total of 279,282,816,000 datapoints. Given the sheer number of figures (, it unsurprising that the data occupies over 500GB in the NetCDF format.

(NB the figures of 20440 and 34675 days are gleaned from the metadata files. I presume that these figures are roundings since they exclude the extra days in leap years, but have not verified this).
    
##Data storage

To import this data at this granularity into a simple database will be challenging - e.g. I first thought of a PostGIS database. Obviously we would we would want to avoid having 279 thousand million rows. Without being able to perform calculations against the entire range of measurement values present, its hard to know how much normalisation might be possible.


 
##Acquiring the data

I copied the data to my own storage space using the following commands.

For historical data (1950 - 2005) for tasmin, tasmax and pr (NB executing the following commands will consume your bandwidth and storage to the tune of 1xxGB):
               
declare -i i; i=1950; while [ $i -lt 2006 ]; do wget http://dataserver3.nccs.nasa.gov/thredds/fileServer/NEX-GDDP/IND/historical/day/atmos/tasmax/r1i1p1/v1.0/tasmax_day_BCSD_historical_r1i1p1_inmcm4_$i.nc; j=$i+1; i=$j; done;

declare -i i; i=1950; while [ $i -lt 2006 ]; do wget http://dataserver3.nccs.nasa.gov/thredds/fileServer/NEX-GDDP/IND/historical/day/atmos/tasmin/r1i1p1/v1.0/tasmin_day_BCSD_historical_r1i1p1_inmcm4_$i.nc; j=$i+1; i=$j; done;

declare -i i; i=1950; while [ $i -lt 2006 ]; do wget http://dataserver3.nccs.nasa.gov/thredds/fileServer/NEX-GDDP/IND/historical/day/atmos/pr/r1i1p1/v1.0/pr_day_BCSD_historical_r1i1p1_inmcm4_$i.nc; j=$i+1; i=$j; done;

(I have not yet acquired the RCP45 and RCP85 datasets).

##How to manipulate the data

In order to provide access to individual datapoints before deciding how best process and import to a database, the API currently uses perl's PDL data structure, since the module PDL::NetCDF http://search.cpan.org/~dhunt/PDL-NetCDF/netcdf.pd provides a straightforward way to convert the contents of a single NetCDF file to a piddle.

Since each NetCDF file represents one measurement for one year, each request for a given year or measurement requires loading a single ~700MB NetCDF file into memory as a piddle.

##Future developments

###Web-scale queries
    
Clearly a desireable use case for the API is to retrieve data for much larger timescales than one or a small number of years.

I'm currently considering how best to process the data in each NetCDF and import it to a database for more complex queries.  Any contributions or suggestions on the most useful and viable ways to provide pre-processed data derived from the raw files and exported to PostGIS are welcome.

###Deferred or post-processed queries

I'm also thinking about how to use the simple API to run a pipeline which generates heatmap images for days / years for each measurement. This could take the form of heatmap.js running in nodejs, for example. 