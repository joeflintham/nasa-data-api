#!/usr/bin/env perl
use constant LIB_DIR => "../../perl5/lib/perl5";
use constant DATA_DIR => "../../data/";

use lib LIB_DIR;

# third party
use Mojolicious::Lite;
use PDL;
use PDL::NetCDF;
use Data::Dump qw(dump);
use Mojo::JSON qw(decode_json encode_json);
use DateTime;
use Try::Tiny;

# local
# TODO: farm out key processes to .pms  

# serves the HTML page
get '/' => sub {
    my $c = shift;
    $c->render();
} => "index";

# serves the (currently) single API endpoint
# TODO: this is a catch-all endpoint with years / measures / lat/lon ranges as get arguments;
# - break this into separate API endppoints for specialised queries
# - e.g....
# - get by month?
# - average by latitude / longitude?
# - average by year / decade / etc
# - GeoJSON queries?
# - etc
get '/api' => sub {
    
    my $c = shift;
    
    $PDL::BIGPDL = 1;

    # in the absence of specified measure(s), use "tasmin"
    my @measures = ("tasmin");
    # accept get param measures as a comma-separated list of measures
    # (known supported measures include "tasmin", "tasmax" and "pr")
    @measures = split(/,/, $c->param('measures')) if ($c->param('measures'));

    # in the absence of specified year(s), use "2005"
    my @years = (2005);
    # accept get param years as a comma-separated list of years to process
    # (leaving the option to specify hyphen-separated ranges)
    @years = split(/,/, $c->param('years')) if $c->param('years');
    
    # in the absence of specified lat / lon bounding box coords, use 0-0.25 x 180-180.25 
    my $latMin = $c->param('latmin') || 0;
    my $lonMin = $c->param('lonmin') || 180;
    my $latMax = $c->param('latmax') || $latMin + 0.25;
    my $lonMax = $c->param('lonmax') || $lonMin + 0.25;

    # define the lat / lon grid used in the .nc files
    # these are normalised across the data set
    # so we are fairly secure in defining these wihtout the cost of loading a file to extract them

    # lats: 720 points starting at -89.875 with 0.25 increments
    my @lats;
    my $lat = -89.875;    
    while (scalar @lats < 720){
        push @lats, $lat;
        $lat += 0.25;
    }
    
    # lons: 1440 points starting at 0.125 with 0.25 increments
    my @lons;
    my $lon = 0.125;    
    while (scalar @lons < 1440){
        push @lons, $lon;
        $lon += 0.25;
    }

    # calculate the positions on the bounding box in the lat / lon grid
    # we're working out the indeces for the given lat/lon coords in the box above
    # I prefer to avoid iterating over long arrays if at all possible
    # and in this case it is not necessary
    my $latMinPos = int(floor(($latMin - (-90)) / 0.25));
    my $lonMinPos = int(ceil(($lonMin) / 0.25));
    my $latMaxPos = int(floor(($latMax - (-90)) / 0.25));
    my $lonMaxPos = int(ceil(($lonMax) / 0.25));

    # placeholder for data response objects
    my $data; # the JSON response for the data retrieved
    my %dataArray; # a hash list of data responses (the file name will be the key to each item)

    try {

        # get the range (i.e. length) of the lat / lon dimensions to be retrieved
        # throw if the error is too big, set a hard floor of +1;
        my $x = $latMaxPos - $latMinPos;
        my $y = $lonMaxPos - $lonMinPos;
        
        if ($x * $y > 225) { # a grid of 15 * 15
            Mojo::Exception->throw("Lat / lon grid too big (max 225 cells)");
        }

        if ($x < 1) { $x = 1; }
        if ($y < 1) { $y = 1; }

        # nested loop is going to be the most memory efficient way to do this since each innermost loop opens a separate >760MB file
        # step through the years first
        foreach my $year (@years){

            # step through the measures for each year
            foreach my $measure (@measures){

                # placeholder for the list of datapoints
                # the date will be the key for each item
                my %dataHash; # a hash of data
                
                # file handle for the measure / year in question
                my $period = "historical";
                # the nasa data has historical data up to and including 2005
                # everything after that is RCP45 / RCP85 projection
                $period = "future" if $year > 2005;
                my $fileName = sprintf ("%1\$s_day_BCSD_%2\$s_r1i1p1_inmcm4_%3\$s.nc", ($measure, $period, $year));

                # throw if the file name does not exist
                my $filePath = DATA_DIR . $fileName;
                if (! -e $filePath) {
                    Mojo::Exception->throw("Can't find file: $filePath");
                }

                # instantiate a netcdf hanlder
                my $ncobj = PDL::NetCDF->new ($filePath);

                # get a piddle of the times - this will provide the number of days in the year
                my $times = $ncobj->get('time');            
                my $days = $times->dim(0); # 365 or 366 presumably

                # retrieve a piddle of the measure according to the dimensions specified
                my $values = $ncobj->get($measure, [0,$latMinPos,$lonMinPos], [$days,$x,$y]);
                
                # turn it into nested array references 
                my @values = unpdl $values;
                
                # iterate through all the days
                my $i = 0;
                while ($i < $days){

                    # generate a datetime for this day
                    my $day = $i + 1;
                    my $dt = DateTime->from_day_of_year(
                        year => $year,
                        day_of_year => $day
                        );

                    # generate the JSON object for this day
                    $dataHash{$dt} = { 
                        "date" => $dt, # extra redundant reference to the date for ui ease
                        "$measure" => $values[0]->[$i] # the data at this point; for >1x>1 matrices, this will be a 2D array; otherwise a scalar
                    };
                    
                    ++$i;
                }

                # add to the accumulator
                # take the opportunity to sort by key (ISO date)  so that the JSON response data is in a sensible order
                $dataArray{$fileName} = sub {
                    my @r;
                    # the ISO datetime string has the advantage of being ASCII sortable
                    foreach my $name (sort {lc $a cmp lc $b} keys %dataHash) {
                        push @r, $dataHash{$name};
                    }
                    return \@r;
                }->();
                
                # close the netcdf handle
                $ncobj->close();

            }
        }
        
        # create a JSON repsonse with the data and include context metadata too
        $data = encode_json {
            metadata => {
                "dimensions" => $x."x".$y,   # the shape of the measure matrix 
                "granularity" => "0.25",     # the granularity of lat / lon coord system for this data
                "period" => \@years,         # a list of one or more years represented by the data
                "measures" => \@measures,    # a list of one or more measures represented by the data
                "boundingbox" => [           # a list of the lat / lon coords specifying the outerbounds of the data (lx,ty/rx,by)
                                             $lats[$latMinPos],       # lx = left lat
                                             $lons[$lonMinPos],       # ty = top lon
                                             $lats[$latMaxPos],       # rx = left lat
                                             $lons[$lonMaxPos]        # by = bottom lon
                    ]  
            }, 
                    data => \%dataArray      # the data for this request 
        };
        
    } catch { # catch errors and report them to the UI

        # generate a JSON repsonse for the error
        $data = encode_json {
            "error" => $_ # report the error
        };
    };
    
    $c->render(resp => $data);
    
} => 'resp';


app->start;
__DATA__

@@resp.html.ep
<%= $resp %>

@@index.html.ep
<h1>Hello world</h1>
